// The app's single source of truth: fetches on a timer, keeps the last good
// status so a Nightscout outage ages into STALE instead of freezing.

import Foundation
import LightkeeperCore
import SwiftUI

@MainActor
final class GlucoseModel: ObservableObject {
    @Published private(set) var status = Status.empty
    /// What the screen draws. The glance, the panel preview and the
    /// VoiceOver label all come from this one value.
    @Published private(set) var presentation = ScreenPresentation(status: .empty)
    @Published private(set) var fetchError = false
    /// When the app last asked Nightscout, by the model's clock.
    @Published private(set) var lastRefresh: Date?
    /// When the current outage began: the first failed fetch after a good
    /// one (or after launch). Kept while fetches keep failing, cleared by the
    /// next good fetch.
    @Published private(set) var offlineSince: Date?
    /// True while a refresh someone asked for (pull to refresh, a settings
    /// save) is running. The timer's refreshes never set it, so nothing on
    /// screen changes once a minute just because the app checked.
    @Published private(set) var isChecking = false
    @Published var settings: Settings {
        didSet {
            // Another site's last reading must never age on this site's screen.
            if settings.nightscoutURL != oldValue.nightscoutURL { forget() }
        }
    }

    /// The exact lines an e-ink panel would show (renderLines).
    var lines: [String] { presentation.lines }

    /// False until a usable Nightscout address is saved. The app then shows
    /// the setup card and never fetches.
    var isConfigured: Bool { settings.isConfigured }

    private var lastGood: Status?
    private var timer: Task<Void, Never>?
    private var checksRunning = 0
    private let now: () -> Int64
    private let fetch: (Settings) async throws -> [Any]

    /// Raw Nightscout entries, or a throw when the URL is not set yet.
    static func fetchFromNightscout(_ settings: Settings) async throws -> [Any] {
        struct NotConfigured: Error {}
        guard let client = settings.makeClient() else { throw NotConfigured() }
        return try await client.fetchEntries()
    }

    /// The app uses the defaults; tests pass a fixed clock and a fake fetch.
    init(settings: Settings = .load(),
         now: @escaping () -> Int64 = { Int64(Date().timeIntervalSince1970 * 1000) },
         fetch: @escaping (Settings) async throws -> [Any] = GlucoseModel.fetchFromNightscout) {
        self.settings = settings
        self.now = now
        self.fetch = fetch
    }

    /// Refresh now, then every 60 seconds while the app is open.
    func start() async {
        timer?.cancel()
        timer = Task { [weak self] in
            while !Task.isCancelled {
                await self?.refresh()
                try? await Task.sleep(for: .seconds(60))
            }
        }
    }

    /// Re-run the pure rules against the clock without a network round trip.
    ///
    /// Called when the app returns to the foreground: after hours in the
    /// background the last screen would otherwise sit there reading "3 min
    /// ago" until the first fetch completes (HAZ-008). This is instant.
    func reclassify() {
        show(classify(lastGood?.reading, nowMs: now(), thresholds: settings.thresholds),
             fetchError: fetchError)
    }

    /// A refresh someone asked for: the same fetch, with "checking
    /// Nightscout..." on screen until it finishes.
    func refreshNow() async {
        checksRunning += 1
        isChecking = true
        await refresh()
        checksRunning -= 1
        isChecking = checksRunning > 0
    }

    func refresh() async {
        // Not set up yet: nothing to ask, and nothing to show but NO DATA
        // behind the setup card. A failed fetch here would read as an outage.
        guard settings.isConfigured else {
            forget()
            return
        }
        let asked = settings
        let result: Result<[Any], Error>
        do { result = .success(try await fetch(asked)) } catch { result = .failure(error) }
        // The site changed while this fetch ran: its answer belongs to the
        // old site, so it is dropped, and the refresh the save started shows
        // the new one.
        guard settings.nightscoutURL == asked.nightscoutURL else { return }
        let nowMs = now()
        let outcome = currentStatus(entries: result, nowMs: nowMs, thresholds: settings.thresholds,
                                    lastGood: lastGood)
        if outcome.fetchError {
            if offlineSince == nil { offlineSince = date(nowMs) }
        } else {
            lastGood = outcome.status
            offlineSince = nil
        }
        show(outcome.status, fetchError: outcome.fetchError)
        lastRefresh = date(nowMs)
    }

    private func show(_ status: Status, fetchError: Bool) {
        self.status = status
        self.fetchError = fetchError
        presentation = ScreenPresentation(status: status, fetchError: fetchError)
    }

    /// Drop everything learned from the current site: back to the first-launch screen.
    private func forget() {
        lastGood = nil
        offlineSince = nil
        lastRefresh = nil
        show(.empty, fetchError: false)
    }

    private func date(_ ms: Int64) -> Date {
        Date(timeIntervalSince1970: Double(ms) / 1000)
    }
}

/// Nightscout URL and display thresholds. The token lives in the Keychain,
/// never in UserDefaults.
struct Settings {
    var nightscoutURL: String = ""
    var urgentLow = 55
    var low = 70
    var high = 180
    var urgentHigh = 250
    var staleMinutes = 15

    /// The thresholds step this far, in mg/dL, on the settings screen.
    static let thresholdStep = 5
    /// Stale after, in minutes: never below one reading interval plus a
    /// minute, and never above an hour (D16 decides whether to lower the cap).
    static let staleRange = 6...60
    /// Above this many minutes the settings screen shows a caution.
    static let staleCautionAbove = 15

    /// The validated thresholds, or nil with the reason when the combination
    /// is impossible (for example low above high). The settings screen
    /// refuses to save an invalid set, and `load()` resets one it finds on
    /// disk, so the display never silently runs on numbers other than the
    /// ones the settings screen shows (HAZ-006).
    var validation: Result<Thresholds, Error> {
        Result {
            try Thresholds(urgentLow: urgentLow, low: low, high: high, urgentHigh: urgentHigh,
                           staleAfterMs: Int64(staleMinutes) * 60_000)
        }
    }

    var isValid: Bool {
        if case .success = validation { return true }
        return false
    }

    var validationMessage: String? {
        guard case .failure(let error) = validation else { return nil }
        switch error as? Thresholds.ValidationError {
        case .outOfOrder:
            return "Thresholds must increase: urgent low < low < high < urgent high."
        case .staleLimitNotPositive:
            return "Stale limit must be at least one minute."
        case nil:
            return "Thresholds are not valid."
        }
    }

    var thresholds: Thresholds {
        // Only reachable with a valid set: save() refuses invalid ones and
        // load() resets them. The fallback is for a tampered UserDefaults.
        (try? validation.get()) ?? .defaults
    }

    /// Why the Nightscout address cannot be used, in plain words, from
    /// NightscoutClient's own check; nil when it is usable or not entered yet.
    var urlProblem: String? {
        guard !nightscoutURL.isEmpty else { return nil }
        do {
            _ = try NightscoutClient(baseURL: nightscoutURL, token: nil)
            return nil
        } catch NightscoutError.badURL(let reason) {
            return reason
        } catch {
            return "This address cannot be used."
        }
    }

    /// True once a usable address is set: the only state in which the app fetches.
    var isConfigured: Bool { !nightscoutURL.isEmpty && urlProblem == nil }

    /// Save is allowed only for valid thresholds and an address that is
    /// usable or empty.
    var canSave: Bool { isValid && urlProblem == nil }

    /// A caution for a long stale limit: an old number keeps looking current
    /// for longer. Nil at 15 minutes or less.
    var staleCaution: String? {
        guard staleMinutes > Self.staleCautionAbove else { return nil }
        return "Above 15 minutes, an old reading keeps looking current for longer before "
            + "this display says STALE. The primary CGM app's signal-loss alert is the one to rely on."
    }

    func resettingThresholds() -> Settings {
        var s = self
        let d = Settings()
        s.urgentLow = d.urgentLow; s.low = d.low; s.high = d.high
        s.urgentHigh = d.urgentHigh; s.staleMinutes = d.staleMinutes
        return s
    }

    func makeClient() -> NightscoutClient? {
        guard !nightscoutURL.isEmpty else { return nil }
        return try? NightscoutClient(baseURL: nightscoutURL, token: Keychain.readToken())
    }

    static func load(from d: UserDefaults = .standard) -> Settings {
        var s = Settings()
        s.nightscoutURL = d.string(forKey: "nightscoutURL") ?? ""
        for (key, path) in [("urgentLow", \Settings.urgentLow), ("low", \.low), ("high", \.high),
                            ("urgentHigh", \.urgentHigh), ("staleMinutes", \.staleMinutes)] {
            if d.object(forKey: key) != nil { s[keyPath: path] = d.integer(forKey: key) }
        }
        // Never start on an invalid set: reset to defaults so the screen and
        // the rules agree, rather than showing one thing and using another.
        // The reset is written back even when the stored address is one the
        // app no longer accepts; that address stays, for Settings to explain.
        if !s.isValid {
            s = s.resettingThresholds()
            s.write(to: d)
        }
        return s
    }

    /// Persist the settings. Returns false, writing nothing, when the
    /// thresholds are invalid or the address cannot be used.
    @discardableResult
    func save(to d: UserDefaults = .standard) -> Bool {
        guard canSave else { return false }
        write(to: d)
        return true
    }

    private func write(to d: UserDefaults) {
        d.set(nightscoutURL, forKey: "nightscoutURL")
        d.set(urgentLow, forKey: "urgentLow")
        d.set(low, forKey: "low")
        d.set(high, forKey: "high")
        d.set(urgentHigh, forKey: "urgentHigh")
        d.set(staleMinutes, forKey: "staleMinutes")
    }
}

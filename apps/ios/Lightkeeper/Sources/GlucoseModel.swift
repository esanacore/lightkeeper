// The app's single source of truth: fetches on a timer, keeps the last good
// status so a Nightscout outage ages into STALE instead of freezing.

import Foundation
import LightkeeperCore
import SwiftUI

@MainActor
final class GlucoseModel: ObservableObject {
    @Published private(set) var status = Status.empty
    @Published private(set) var lines: [String] = ["NO DATA", "Check sensor and phone", "Confirm on primary device"]
    @Published private(set) var fetchError = false
    @Published private(set) var lastRefresh: Date?
    @Published var settings: Settings

    private var lastGood: Status?
    private var timer: Task<Void, Never>?
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
        status = classify(lastGood?.reading, nowMs: now(), thresholds: settings.thresholds)
        lines = renderLines(status, fetchError: fetchError)
    }

    func refresh() async {
        let thresholds = settings.thresholds
        let result: Result<[Any], Error>
        do { result = .success(try await fetch(settings)) } catch { result = .failure(error) }
        let outcome = currentStatus(entries: result, nowMs: now(), thresholds: thresholds, lastGood: lastGood)
        if !outcome.fetchError { lastGood = outcome.status }
        status = outcome.status
        fetchError = outcome.fetchError
        lines = renderLines(outcome.status, fetchError: outcome.fetchError)
        lastRefresh = Date()
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
        if !s.isValid { s = s.resettingThresholds(); s.save(to: d) }
        return s
    }

    /// Persist the settings. Returns false, writing nothing, when the
    /// thresholds are invalid.
    @discardableResult
    func save(to d: UserDefaults = .standard) -> Bool {
        guard isValid else { return false }
        d.set(nightscoutURL, forKey: "nightscoutURL")
        d.set(urgentLow, forKey: "urgentLow")
        d.set(low, forKey: "low")
        d.set(high, forKey: "high")
        d.set(urgentHigh, forKey: "urgentHigh")
        d.set(staleMinutes, forKey: "staleMinutes")
        return true
    }
}

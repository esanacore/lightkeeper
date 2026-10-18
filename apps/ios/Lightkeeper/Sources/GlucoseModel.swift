// The app's single source of truth: fetches on a timer, keeps the last good
// status so a Nightscout outage ages into STALE instead of freezing.

import Foundation
import LightkeeperCore
import SwiftUI

@MainActor
final class GlucoseModel: ObservableObject {
    @Published private(set) var status = Status(level: .noData, reading: nil, ageMs: nil)
    @Published private(set) var lines: [String] = ["NO DATA", "Check sensor and phone", "Confirm on primary device"]
    @Published private(set) var fetchError = false
    @Published private(set) var lastRefresh: Date?
    @Published var settings = Settings.load()

    private var lastGood: Status?
    private var timer: Task<Void, Never>?

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

    func refresh() async {
        let now = Int64(Date().timeIntervalSince1970 * 1000)
        let thresholds = settings.thresholds
        let result: Result<[Any], Error>
        if let client = settings.makeClient() {
            do { result = .success(try await client.fetchEntries()) } catch { result = .failure(error) }
        } else {
            struct NotConfigured: Error {}
            result = .failure(NotConfigured())
        }
        let outcome = currentStatus(entries: result, nowMs: now, thresholds: thresholds, lastGood: lastGood)
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

    var thresholds: Thresholds {
        (try? Thresholds(urgentLow: urgentLow, low: low, high: high, urgentHigh: urgentHigh,
                         staleAfterMs: Int64(staleMinutes) * 60_000)) ?? .defaults
    }

    func makeClient() -> NightscoutClient? {
        guard !nightscoutURL.isEmpty else { return nil }
        return try? NightscoutClient(baseURL: nightscoutURL, token: Keychain.readToken())
    }

    static func load() -> Settings {
        let d = UserDefaults.standard
        var s = Settings()
        s.nightscoutURL = d.string(forKey: "nightscoutURL") ?? ""
        for (key, path) in [("urgentLow", \Settings.urgentLow), ("low", \.low), ("high", \.high),
                            ("urgentHigh", \.urgentHigh), ("staleMinutes", \.staleMinutes)] {
            if d.object(forKey: key) != nil { s[keyPath: path] = d.integer(forKey: key) }
        }
        return s
    }

    func save() {
        let d = UserDefaults.standard
        d.set(nightscoutURL, forKey: "nightscoutURL")
        d.set(urgentLow, forKey: "urgentLow")
        d.set(low, forKey: "low")
        d.set(high, forKey: "high")
        d.set(urgentHigh, forKey: "urgentHigh")
        d.set(staleMinutes, forKey: "staleMinutes")
    }
}

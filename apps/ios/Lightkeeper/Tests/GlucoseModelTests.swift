// HAZ-001 / HAZ-008: coming back to the foreground re-ages the last reading
// against the clock at once, without waiting for a fetch, so a reading that
// went stale in the background is shown as STALE immediately. Also: the
// outage caption's start time, the setup state that never fetches, and the
// one presentation every part of the screen is drawn from.

import LightkeeperCore
import XCTest
@testable import Lightkeeper

@MainActor
final class GlucoseModelTests: XCTestCase {
    /// 2026-10-18T12:00:00Z, the same fixed clock the other suites use.
    private let t0: Int64 = 1_792_324_800_000
    private let minute: Int64 = 60_000

    private final class Clock {
        var nowMs: Int64
        init(_ nowMs: Int64) { self.nowMs = nowMs }
    }

    /// A mutable cell a fetch closure can share with the test.
    private final class Box<Value> {
        var value: Value
        init(_ value: Value) { self.value = value }
    }

    private nonisolated func entry(mgdl: Int, at ms: Int64) -> [String: Any] {
        ["type": "sgv", "sgv": mgdl, "date": Double(ms), "direction": "Flat"]
    }

    /// Settings with a usable address: the only state in which the model fetches.
    private nonisolated func configured(_ url: String = "https://ns.example.com") -> Settings {
        var settings = Settings()
        settings.nightscoutURL = url
        return settings
    }

    private func date(_ ms: Int64) -> Date {
        Date(timeIntervalSince1970: Double(ms) / 1000)
    }

    func testReclassifyTurnsAnOldReadingStaleWithoutFetching() async {
        let clock = Clock(t0)
        var fetches = 0
        let reading = entry(mgdl: 112, at: t0 - 2 * minute)
        let model = GlucoseModel(settings: configured(), now: { clock.nowMs }, fetch: { _ in
            fetches += 1
            return [reading]
        })

        await model.refresh()
        XCTAssertEqual(model.status.level, .inRange)
        XCTAssertEqual(model.lines[2], "2 min ago")
        XCTAssertEqual(fetches, 1)

        // Hours in the background; no fetch has happened yet.
        clock.nowMs = t0 + 3 * 60 * minute
        model.reclassify()
        XCTAssertEqual(model.status.level, .stale)
        XCTAssertEqual(model.lines.first, "STALE - DO NOT TRUST")
        XCTAssertEqual(model.presentation.banner, .stale)
        XCTAssertEqual(model.presentation.hero, .none, "no large number once it is old")
        XCTAssertEqual(fetches, 1, "reclassify must not touch the network")
    }

    func testReclassifyUsesTheSettingsStaleLimit() async {
        let clock = Clock(t0)
        var settings = configured()
        settings.staleMinutes = 10
        let reading = entry(mgdl: 120, at: t0)
        let model = GlucoseModel(settings: settings, now: { clock.nowMs }, fetch: { _ in [reading] })
        await model.refresh()

        clock.nowMs = t0 + 10 * minute
        model.reclassify()
        XCTAssertEqual(model.status.level, .inRange, "exactly at the limit is still fresh")

        clock.nowMs = t0 + 11 * minute
        model.reclassify()
        XCTAssertEqual(model.status.level, .stale)
    }

    func testReclassifyBeforeAnyFetchShowsNoData() {
        let model = GlucoseModel(settings: configured(), now: { self.t0 }, fetch: { _ in [] })
        model.reclassify()
        XCTAssertEqual(model.status.level, .noData)
    }

    func testFailedFetchKeepsAgingTheLastGoodReading() async {
        let clock = Clock(t0)
        struct Down: Error {}
        var fail = false
        let reading = entry(mgdl: 101, at: t0)
        let model = GlucoseModel(settings: configured(), now: { clock.nowMs }, fetch: { _ in
            if fail { throw Down() }
            return [reading]
        })
        await model.refresh()

        fail = true
        clock.nowMs = t0 + 30 * minute
        await model.refresh()
        XCTAssertTrue(model.fetchError)
        XCTAssertEqual(model.status.level, .stale)
        XCTAssertEqual(model.lines.last, "Nightscout unreachable")
    }

    func testOfflineSinceIsSetOnTheFirstFailureKeptOnRepeatsAndClearedOnSuccess() async {
        let clock = Clock(t0)
        struct Down: Error {}
        var fail = false
        let model = GlucoseModel(settings: configured(), now: { clock.nowMs }, fetch: { _ in
            if fail { throw Down() }
            return [self.entry(mgdl: 110, at: clock.nowMs)]
        })
        await model.refresh()
        XCTAssertNil(model.offlineSince)
        XCTAssertEqual(model.lastRefresh, date(t0))

        fail = true
        clock.nowMs = t0 + 1 * minute
        await model.refresh()
        XCTAssertEqual(model.offlineSince, date(t0 + 1 * minute), "set on the first failure")

        clock.nowMs = t0 + 2 * minute
        await model.refresh()
        clock.nowMs = t0 + 3 * minute
        await model.refresh()
        XCTAssertEqual(model.offlineSince, date(t0 + 1 * minute), "kept while failures repeat")
        XCTAssertEqual(model.lastRefresh, date(t0 + 3 * minute), "checked is every attempt")

        fail = false
        clock.nowMs = t0 + 4 * minute
        await model.refresh()
        XCTAssertNil(model.offlineSince, "cleared on success")
        XCTAssertFalse(model.fetchError)

        fail = true
        clock.nowMs = t0 + 9 * minute
        await model.refresh()
        XCTAssertEqual(model.offlineSince, date(t0 + 9 * minute), "a new outage starts afresh")
    }

    func testNotConfiguredMakesNoFetch() async {
        for url in ["", "http://ns.example.com", "https://ns.example.com/nightscout"] {
            var fetches = 0
            var settings = Settings()
            settings.nightscoutURL = url
            let model = GlucoseModel(settings: settings, now: { self.t0 }, fetch: { _ in
                fetches += 1
                return []
            })
            XCTAssertFalse(model.isConfigured, url)
            await model.refresh()
            await model.refreshNow()
            model.reclassify()
            XCTAssertEqual(fetches, 0, "\(url): no fetch before a usable address is saved")
            XCTAssertEqual(model.status.level, .noData, url)
            XCTAssertFalse(model.fetchError, "\(url): not set up is not an outage")
            XCTAssertNil(model.offlineSince, url)
            XCTAssertNil(model.lastRefresh, url)
            XCTAssertEqual(model.lines, renderLines(.empty), "\(url): the panel preview keeps the vector lines")
        }
    }

    func testSavingAnAddressStartsFetching() async {
        var fetches = 0
        let reading = entry(mgdl: 140, at: t0)
        let model = GlucoseModel(settings: Settings(), now: { self.t0 }, fetch: { _ in
            fetches += 1
            return [reading]
        })
        await model.refresh()
        XCTAssertEqual(fetches, 0)
        model.settings = configured()
        XCTAssertTrue(model.isConfigured)
        await model.refreshNow()
        XCTAssertEqual(fetches, 1)
        XCTAssertEqual(model.status.level, .inRange)
    }

    func testChangingTheSiteForgetsTheOldSitesReading() async {
        struct Down: Error {}
        var fail = false
        let reading = entry(mgdl: 99, at: t0)
        let model = GlucoseModel(settings: configured("https://a.example.com"), now: { self.t0 },
                                 fetch: { _ in
            if fail { throw Down() }
            return [reading]
        })
        await model.refresh()
        XCTAssertEqual(model.status.level, .inRange)

        fail = true
        model.settings = configured("https://b.example.com")
        XCTAssertEqual(model.status.level, .noData, "the old site's reading is gone at once")
        XCTAssertNil(model.lastRefresh)
        await model.refresh()
        XCTAssertEqual(model.status.level, .noData, "and a failure on the new site never brings it back")
        XCTAssertEqual(model.lines.last, "Nightscout unreachable")

        // Changing only the thresholds keeps the reading.
        fail = false
        await model.refresh()
        var stricter = model.settings
        stricter.low = 100
        model.settings = stricter
        XCTAssertNotNil(model.lastRefresh)
        model.reclassify()
        XCTAssertEqual(model.status.level, .low, "the same reading, under the new thresholds")
    }

    func testAnAnswerForTheOldSiteIsDropped() async {
        let holder = Box<GlucoseModel?>(nil)
        let moved = configured("https://b.example.com")
        let reading = entry(mgdl: 99, at: t0)
        let model = GlucoseModel(settings: configured("https://a.example.com"), now: { self.t0 },
                                 fetch: { _ in
            // The person saves a new site while this fetch is in flight.
            await MainActor.run { holder.value?.settings = moved }
            return [reading]
        })
        holder.value = model
        await model.refresh()
        holder.value = nil
        XCTAssertEqual(model.status.level, .noData, "the old site's answer is never shown")
        XCTAssertNil(model.lastRefresh)
        XCTAssertEqual(model.settings.nightscoutURL, "https://b.example.com")
    }

    func testRefreshNowShowsCheckingOnlyWhileItRuns() async {
        let holder = Box<GlucoseModel?>(nil)
        let seen = Box<[Bool]>([])
        let reading = entry(mgdl: 120, at: t0)
        let model = GlucoseModel(settings: configured(), now: { self.t0 }, fetch: { _ in
            let checking = await MainActor.run { holder.value?.isChecking ?? false }
            seen.value.append(checking)
            return [reading]
        })
        holder.value = model
        XCTAssertFalse(model.isChecking)
        await model.refreshNow()
        XCTAssertFalse(model.isChecking, "cleared when the fetch finishes")
        await model.refresh()
        holder.value = nil
        XCTAssertEqual(seen.value, [true, false], "a timer refresh never shows 'checking Nightscout...'")
    }

    /// A timer fetch hangs, a pull to refresh gets through, then the timer
    /// fetch times out: its late failure is older news and is dropped, so
    /// the screen does not say "unreachable since" just after a good fetch.
    func testALateAnswerFromAnOlderFetchIsDropped() async {
        let clock = Clock(t0)
        struct Down: Error {}
        let calls = Box(0)
        let gate = Box<CheckedContinuation<Void, Never>?>(nil)
        let (waiting, signal) = AsyncStream<Void>.makeStream()
        let reading = entry(mgdl: 120, at: t0)
        let model = GlucoseModel(settings: configured(), now: { clock.nowMs }, fetch: { _ in
            calls.value += 1
            guard calls.value == 1 else { return [reading] }
            await withCheckedContinuation { (hang: CheckedContinuation<Void, Never>) in
                gate.value = hang
                signal.yield()
            }
            throw Down()
        })
        let timerFetch = Task { await model.refresh() }
        for await _ in waiting { break }

        clock.nowMs = t0 + 5_000
        await model.refreshNow()
        XCTAssertEqual(model.status.level, .inRange)
        XCTAssertNil(model.offlineSince)

        clock.nowMs = t0 + 10_000
        gate.value?.resume()
        await timerFetch.value
        XCTAssertEqual(calls.value, 2)
        XCTAssertFalse(model.fetchError, "the older fetch's failure is not shown")
        XCTAssertNil(model.offlineSince, "no outage starts just after a good fetch")
        XCTAssertEqual(model.lines, ["IN RANGE", "120 mg/dL ->", "just now"])
        XCTAssertEqual(model.lastRefresh, date(t0 + 5_000))

        // The next fetch is applied as usual.
        clock.nowMs = t0 + 60_000
        await model.refresh()
        XCTAssertEqual(model.lastRefresh, date(t0 + 60_000))
        XCTAssertEqual(calls.value, 3)
    }

    func testThePresentationIsTheOneSourceOfTheScreen() async {
        let clock = Clock(t0)
        struct Down: Error {}
        var fail = false
        let reading = entry(mgdl: 112, at: t0 - 3 * minute)
        let model = GlucoseModel(settings: configured(), now: { clock.nowMs }, fetch: { _ in
            if fail { throw Down() }
            return [reading]
        })
        await model.refresh()
        XCTAssertEqual(model.lines, ["IN RANGE", "112 mg/dL ->", "3 min ago"])
        XCTAssertEqual(model.presentation.accessibilityLabel,
                       "In range. 112 milligrams per deciliter, steady. 3 minutes ago.")
        XCTAssertEqual(model.presentation.hero, .number(digits: "112", arrow: "->", unit: "mg/dL"))

        fail = true
        clock.nowMs = t0 + 20 * minute
        await model.refresh()
        XCTAssertEqual(model.presentation, ScreenPresentation(status: model.status, fetchError: true))
        XCTAssertEqual(model.lines, renderLines(model.status, fetchError: true))
        XCTAssertEqual(model.presentation.accessibilityLabel,
                       spokenText(status: model.status, error: true))
    }
}

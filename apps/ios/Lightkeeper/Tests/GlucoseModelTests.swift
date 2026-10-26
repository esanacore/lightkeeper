// HAZ-001 / HAZ-008: coming back to the foreground re-ages the last reading
// against the clock at once, without waiting for a fetch, so a reading that
// went stale in the background is shown as STALE immediately.

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

    private func entry(mgdl: Int, at ms: Int64) -> [String: Any] {
        ["type": "sgv", "sgv": mgdl, "date": Double(ms), "direction": "Flat"]
    }

    func testReclassifyTurnsAnOldReadingStaleWithoutFetching() async {
        let clock = Clock(t0)
        var fetches = 0
        let reading = entry(mgdl: 112, at: t0 - 2 * minute)
        let model = GlucoseModel(settings: Settings(), now: { clock.nowMs }, fetch: { _ in
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
        XCTAssertEqual(fetches, 1, "reclassify must not touch the network")
    }

    func testReclassifyUsesTheSettingsStaleLimit() async {
        let clock = Clock(t0)
        var settings = Settings()
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
        let model = GlucoseModel(settings: Settings(), now: { self.t0 }, fetch: { _ in [] })
        model.reclassify()
        XCTAssertEqual(model.status.level, .noData)
    }

    func testFailedFetchKeepsAgingTheLastGoodReading() async {
        let clock = Clock(t0)
        struct Down: Error {}
        var fail = false
        let reading = entry(mgdl: 101, at: t0)
        let model = GlucoseModel(settings: Settings(), now: { clock.nowMs }, fetch: { _ in
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
}

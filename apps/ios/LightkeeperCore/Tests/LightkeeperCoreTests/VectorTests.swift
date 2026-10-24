// FR-009 / FR-012: the Swift rules pass every shared vector, so the app
// shows exactly what the Python tool and the firmware show.

import Foundation
import XCTest
@testable import LightkeeperCore

final class VectorTests: XCTestCase {
    struct Entry: Decodable {
        let type: String?
        let sgv: Double?
        let direction: String?
    }
    /// One entry plus its age; exactly one of the two age fields is present.
    struct Item: Decodable {
        let entry: Entry?
        let minutes_ago: Int?
        let seconds_ago: Int?

        var ageMs: Int64? {
            if let s = seconds_ago { return Int64(s) * 1000 }
            return minutes_ago.map { Int64($0) * 60_000 }
        }
    }
    struct CustomThresholds: Decodable {
        let urgent_low: Int
        let low: Int
        let high: Int
        let urgent_high: Int
        let stale_after_minutes: Int
    }
    struct Vector: Decodable {
        let name: String
        let entry: Entry?
        let minutes_ago: Int?
        let seconds_ago: Int?
        let entries: [Item]?
        let thresholds: CustomThresholds?
        let error: String?
        let level: String
        let lines: [String]

        /// Every entry in the case, in either form.
        var items: [Item] {
            entries ?? [Item(entry: entry, minutes_ago: minutes_ago, seconds_ago: seconds_ago)]
        }
    }
    struct Spec: Decodable {
        let spec_version: Int
        let cases: [Vector]
    }

    /// 2026-10-18T12:00:00Z, the same fixed clock the Python tests use.
    let nowMs: Int64 = 1_792_324_800_000

    func loadSpec() throws -> Spec {
        // Walk up from this file until the repository root (the folder holding spec/).
        var url = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
        while !FileManager.default.fileExists(atPath: url.appendingPathComponent("spec").path),
              url.path != "/" {
            url.deleteLastPathComponent()
        }
        let spec = url.appendingPathComponent("spec/display_vectors.json")
        return try JSONDecoder().decode(Spec.self, from: Data(contentsOf: spec))
    }

    func testEveryVectorMatches() throws {
        let spec = try loadSpec()
        XCTAssertEqual(spec.spec_version, 1, "bump this assertion when an existing vector changes")
        XCTAssertGreaterThan(spec.cases.count, 35)

        for v in spec.cases {
            var raws: [Any] = []
            for item in v.items {
                guard let e = item.entry else { continue }
                guard let ageMs = item.ageMs else {
                    XCTFail("vector \(v.name): entry without an age")
                    continue
                }
                var raw: [String: Any] = ["date": Double(nowMs - ageMs)]
                if let t = e.type { raw["type"] = t }
                if let s = e.sgv { raw["sgv"] = s }
                if let d = e.direction { raw["direction"] = d }
                raws.append(raw)
            }
            var thresholds = Thresholds.defaults
            if let c = v.thresholds {
                thresholds = try Thresholds(urgentLow: c.urgent_low, low: c.low, high: c.high,
                                            urgentHigh: c.urgent_high,
                                            staleAfterMs: Int64(c.stale_after_minutes) * 60_000)
            }
            let status = classify(parseEntries(raws).first, nowMs: nowMs, thresholds: thresholds)
            let lines = renderLines(status, fetchError: v.error != nil)
            XCTAssertEqual(status.level.rawValue, v.level, "vector \(v.name): level")
            XCTAssertEqual(lines, v.lines, "vector \(v.name): lines")
        }
    }

    func testBooleansAreNotNumbers() {
        XCTAssertThrowsError(try parseEntry(["sgv": true, "date": 1.0]))
        XCTAssertThrowsError(try parseEntry(["sgv": 120, "date": false]))
    }

    /// HAZ-012: numbers too large for Int must throw, never trap.
    func testHugeNumbersThrowInsteadOfCrashing() {
        XCTAssertThrowsError(try parseEntry(["sgv": 1e30, "date": Double(nowMs)]))
        XCTAssertThrowsError(try parseEntry(["sgv": 120, "date": 1e20]))
        XCTAssertThrowsError(try parseEntry(["sgv": 120, "date": Double(nowMs) / 1000]),
                             "a date in seconds is rejected, not read as 1970")
        XCTAssertNoThrow(try parseEntry(["sgv": 120, "date": Double(nowMs)]))
    }

    /// One malformed entry never hides the good ones around it.
    func testPoisonedEntryDoesNotBlankTheList() {
        let readings = parseEntries([
            ["sgv": Double.nan, "date": Double(nowMs)],
            ["sgv": 120, "date": Double(nowMs - 60_000)],
            ["sgv": 1e30, "date": Double(nowMs)],
        ])
        XCTAssertEqual(readings.map(\.mgdl), [120])
    }

    /// Same timestamp from two uploaders: the lower value wins.
    func testSameTimestampPicksLowerValue() {
        let readings = parseEntries([
            ["sgv": 130, "date": Double(nowMs)],
            ["sgv": 68, "date": Double(nowMs)],
            ["sgv": 110, "date": Double(nowMs - 300_000)],
        ])
        XCTAssertEqual(readings.map(\.mgdl), [68, 130, 110])
    }

    func testThresholdValidation() {
        XCTAssertThrowsError(try Thresholds(urgentLow: 70, low: 70))
        XCTAssertThrowsError(try Thresholds(urgentHigh: 450))
        XCTAssertThrowsError(try Thresholds(staleAfterMs: 0))
        XCTAssertNoThrow(try Thresholds(urgentLow: 60, low: 80, high: 160, urgentHigh: 220))
    }

    func testFetchFailureAgesLastGoodIntoStale() throws {
        let good = classify(GlucoseReading(mgdl: 120, timestampMs: nowMs - 120_000, trend: .flat),
                            nowMs: nowMs, thresholds: .defaults)
        struct Down: Error {}
        let soon = currentStatus(entries: .failure(Down()), nowMs: nowMs + 5 * 60_000,
                                 thresholds: .defaults, lastGood: good)
        XCTAssertEqual(soon.status.level, .inRange)
        XCTAssertTrue(soon.fetchError)
        let later = currentStatus(entries: .failure(Down()), nowMs: nowMs + 30 * 60_000,
                                  thresholds: .defaults, lastGood: good)
        XCTAssertEqual(later.status.level, .stale)
        XCTAssertEqual(renderLines(later.status, fetchError: true).count, maxLines)
    }
}

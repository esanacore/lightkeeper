// FR-009 / FR-012: the Swift rules pass every shared vector, so the app
// shows exactly what the Python tool and the firmware show.

import Foundation
import XCTest
@testable import LightkeeperCore

final class VectorTests: XCTestCase {
    struct Vector: Decodable {
        struct Entry: Decodable {
            let type: String?
            let sgv: Double?
            let direction: String?
        }
        let name: String
        let entry: Entry?
        let minutes_ago: Int
        let error: String?
        let level: String
        let lines: [String]
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
        XCTAssertGreaterThan(spec.cases.count, 20)

        for v in spec.cases {
            var reading: GlucoseReading? = nil
            if let e = v.entry {
                var raw: [String: Any] = ["date": Double(nowMs - Int64(v.minutes_ago) * 60_000)]
                if let t = e.type { raw["type"] = t }
                if let s = e.sgv { raw["sgv"] = s }
                if let d = e.direction { raw["direction"] = d }
                reading = try? parseEntry(raw)
            }
            let status = classify(reading, nowMs: nowMs, thresholds: .defaults)
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

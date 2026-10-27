// FR-017: VoiceOver hears the same sentences Python generates. Every case in
// spec/display_vectors.json is classified here the way VectorTests does it,
// and spokenText must equal its sentence in spec/spoken_vectors.json.

import Foundation
import XCTest
@testable import LightkeeperCore

final class SpokenVectorTests: XCTestCase {
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

        var items: [Item] {
            entries ?? [Item(entry: entry, minutes_ago: minutes_ago, seconds_ago: seconds_ago)]
        }
    }
    struct DisplaySpec: Decodable {
        let cases: [Vector]
    }
    struct SpokenSpec: Decodable {
        let description: String
        let cases: [String: String]
    }

    /// 2026-10-18T12:00:00Z, the same fixed clock the Python tests use.
    let nowMs: Int64 = 1_792_324_800_000

    func specData(_ name: String) throws -> Data {
        // Walk up from this file until the repository root (the folder holding spec/).
        var url = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
        while !FileManager.default.fileExists(atPath: url.appendingPathComponent("spec").path),
              url.path != "/" {
            url.deleteLastPathComponent()
        }
        return try Data(contentsOf: url.appendingPathComponent("spec/\(name)"))
    }

    func status(for v: Vector) throws -> Status {
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
        return classify(parseEntries(raws).first, nowMs: nowMs, thresholds: thresholds)
    }

    func testEverySpokenVectorMatches() throws {
        let display = try JSONDecoder().decode(DisplaySpec.self, from: specData("display_vectors.json"))
        let spoken = try JSONDecoder().decode(SpokenSpec.self, from: specData("spoken_vectors.json"))
        XCTAssertGreaterThan(display.cases.count, 35)
        XCTAssertEqual(Set(spoken.cases.keys), Set(display.cases.map(\.name)),
                       "one spoken sentence per display vector, and no extras")
        XCTAssertEqual(spoken.cases.count, display.cases.count)

        for v in display.cases {
            let status = try status(for: v)
            XCTAssertEqual(status.level.rawValue, v.level, "vector \(v.name): level")
            XCTAssertEqual(spokenText(status: status, error: v.error != nil), spoken.cases[v.name],
                           "vector \(v.name): spoken")
        }
    }

    func reading(_ mgdl: Int = 120, _ trend: Trend = .flat) -> GlucoseReading {
        GlucoseReading(mgdl: mgdl, timestampMs: nowMs, trend: trend)
    }

    func stale(_ mgdl: Int = 120, _ trend: Trend = .flat, minutes: Int64 = 30) -> Status {
        Status(level: .stale, reading: reading(mgdl, trend), ageMs: minutes * 60_000)
    }

    let noData = "No data. Check sensor and phone. Confirm on the primary device."
    let future = "Stale, do not trust. Reading time is in the future. Confirm on the primary device."

    /// The same literal sentences tests/test_spoken.py pins for forms the vectors do not reach.
    func testFormsBeyondTheVectorsMatchPython() {
        XCTAssertEqual(spokenText(status: stale(39, minutes: 20)),
                       "Stale, do not trust. Last reading below 40, 20 minutes ago. "
                       + "Confirm on the primary device.")
        XCTAssertEqual(spokenText(status: stale(401, minutes: 61)),
                       "Stale, do not trust. Last reading above 400, 61 minutes ago. "
                       + "Confirm on the primary device.")
        let levels: [(Level, String)] = [(.urgentLow, "Urgent low."), (.low, "Low."),
                                         (.inRange, "In range."), (.high, "High."),
                                         (.urgentHigh, "Urgent high.")]
        for (level, headline) in levels {
            let status = Status(level: level, reading: reading(150, .singleUp), ageMs: 60_000)
            XCTAssertEqual(spokenText(status: status),
                           "\(headline) 150 milligrams per deciliter, rising. 1 minute ago.")
        }
    }

    func testStaleNeverSpeaksATrendWord() {
        for trend in Trend.allCases {
            let text = spokenText(status: stale(80, trend)).lowercased()
            XCTAssertTrue(text.hasPrefix("stale, do not trust. "), "\(trend)")
            for word in ["rising", "falling", "steady", "trend unknown"] {
                XCTAssertFalse(text.contains(word), "\(trend): \(word)")
            }
        }
    }

    func testWithoutAReadingOrAnAgeItIsSpokenAsNoData() {
        let cases = [
            Status.empty,
            Status(level: .inRange, reading: nil, ageMs: nil),
            Status(level: .stale, reading: reading(), ageMs: nil),
            Status(level: .inRange, reading: reading(), ageMs: nil),
            Status(level: .noData, reading: reading(45), ageMs: 0),
            Status(level: .noData, reading: reading(45), ageMs: 40 * 60_000),
            Status(level: .noData, reading: reading(45), ageMs: -5 * 60_000),
        ]
        for status in cases {
            XCTAssertEqual(spokenText(status: status), noData, "\(status)")
        }
    }

    func testANegativeAgeIsNeverSpokenAsCurrent() {
        for level in [Level.inRange, .urgentLow, .stale] {
            let status = Status(level: level, reading: reading(), ageMs: -3 * 60_000)
            XCTAssertEqual(spokenText(status: status), future, "\(level)")
        }
    }

    func testUnreachableIsAddedLast() {
        for status in [Status.empty, stale(), Status(level: .low, reading: reading(65), ageMs: 0)] {
            XCTAssertEqual(spokenText(status: status, error: true),
                           spokenText(status: status) + " Nightscout unreachable.")
        }
    }

    func testEveryTrendHasItsOwnWords() {
        let expected: [Trend: String] = [
            .doubleUp: "rising quickly", .singleUp: "rising", .fortyFiveUp: "rising slowly",
            .flat: "steady", .fortyFiveDown: "falling slowly", .singleDown: "falling",
            .doubleDown: "falling quickly", .unknown: "trend unknown",
        ]
        for trend in Trend.allCases {
            XCTAssertEqual(trend.spokenName, expected[trend], "\(trend)")
        }
        XCTAssertEqual(spokenAge(0), "just now")
        XCTAssertEqual(spokenAge(1), "1 minute ago")
        XCTAssertEqual(spokenAge(2), "2 minutes ago")
    }
}

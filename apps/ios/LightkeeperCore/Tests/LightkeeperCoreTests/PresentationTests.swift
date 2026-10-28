// HAZ-001 / HAZ-008 / FR-012 / FR-017: the phone's hierarchy, held to every
// display vector. A STALE value is never the hero (no number, no separate
// arrow, no unit), NO DATA never shows a number, every word on the glance is
// a vector line verbatim, and VoiceOver hears exactly spokenText. The shapes
// and colour tokens follow the status table in assets/brand/tokens.json.

import Foundation
import XCTest
@testable import LightkeeperCore

final class PresentationTests: XCTestCase {
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

        var items: [Item] {
            entries ?? [Item(entry: entry, minutes_ago: minutes_ago, seconds_ago: seconds_ago)]
        }
    }
    struct DisplaySpec: Decodable {
        let cases: [Vector]
    }
    struct StatusToken: Decodable {
        let word: String
        let color: String
        let chip: String
        let treatment: String
    }
    struct UnknownToken: Decodable {
        let color: String
        let chip: String
        let treatment: String
    }
    struct Tokens: Decodable {
        let status: [String: StatusToken]
        let unknown_headline: UnknownToken
    }

    /// One display vector with its status and its presentation.
    struct Case {
        let vector: Vector
        let status: Status
        let presentation: ScreenPresentation

        var name: String { vector.name }
        var lines: [String] { vector.lines }
        var reading: GlucoseReading? { status.reading }
        var isSentinel: Bool {
            reading.map { $0.isSensorLowSentinel || $0.isSensorHighSentinel } ?? false
        }
    }

    /// 2026-10-18T12:00:00Z, the same fixed clock the Python tests use.
    let nowMs: Int64 = 1_792_324_800_000

    func repoFile(_ path: String) throws -> Data {
        // Walk up from this file until the repository root (the folder holding spec/).
        var url = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
        while !FileManager.default.fileExists(atPath: url.appendingPathComponent("spec").path),
              url.path != "/" {
            url.deleteLastPathComponent()
        }
        return try Data(contentsOf: url.appendingPathComponent(path))
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

    func cases() throws -> [Case] {
        let spec = try JSONDecoder().decode(DisplaySpec.self, from: repoFile("spec/display_vectors.json"))
        XCTAssertGreaterThan(spec.cases.count, 35)
        return try spec.cases.map { v in
            let status = try status(for: v)
            XCTAssertEqual(status.level.rawValue, v.level, "vector \(v.name): level")
            return Case(vector: v, status: status,
                        presentation: ScreenPresentation(status: status, fetchError: v.error != nil))
        }
    }

    func cases(_ levels: Level...) throws -> [Case] {
        let wanted = Set(levels.map(\.rawValue))
        let found = try cases().filter { wanted.contains($0.status.level.rawValue) }
        XCTAssertFalse(found.isEmpty, "no vectors for \(levels)")
        return found
    }

    // MARK: Every vector

    func testFreshNumericVectorsGiveTheVectorsDigitsAndArrowAndNoBanner() throws {
        for c in try cases(.inRange, .low, .high) where !c.isSentinel {
            let reading = try XCTUnwrap(c.reading, c.name)
            let p = c.presentation
            XCTAssertEqual(p.hero, .number(digits: String(reading.mgdl), arrow: reading.trend.arrow,
                                           unit: "mg/dL"), c.name)
            guard case .number(let digits, let arrow, let unit) = p.hero else { continue }
            XCTAssertEqual("\(digits) \(unit) \(arrow)", c.lines[1],
                           "\(c.name): the hero is the vector's value line, cut in three")
            XCTAssertEqual(p.hero.arrowSymbol, reading.trend.symbol, c.name)
            XCTAssertEqual(p.banner, .none, c.name)
            XCTAssertNil(p.secondary, c.name)
            XCTAssertEqual(p.age, c.lines[2], c.name)
        }
    }

    func testUrgentVectorsGiveTheUrgentBanner() throws {
        for c in try cases(.urgentLow, .urgentHigh) {
            let p = c.presentation
            XCTAssertEqual(p.banner, .urgent, c.name)
            XCTAssertEqual(p.chip.word, c.lines[0], c.name)
            XCTAssertEqual(p.chip.tone, c.status.level == .urgentLow ? .low : .high, c.name)
            XCTAssertEqual(p.age, c.lines[2], "\(c.name): the age is never dropped")
            if !c.isSentinel {
                let reading = try XCTUnwrap(c.reading, c.name)
                XCTAssertEqual(p.hero, .number(digits: String(reading.mgdl),
                                               arrow: reading.trend.arrow, unit: "mg/dL"), c.name)
            }
        }
    }

    func testStaleVectorsGiveTheStaleBannerNoHeroAndAStruckLastLine() throws {
        for c in try cases(.stale) {
            let p = c.presentation
            XCTAssertEqual(p.banner, .stale, c.name)
            XCTAssertEqual(p.hero, .none, "\(c.name): an old value is never the hero")
            XCTAssertNil(p.hero.arrowSymbol, "\(c.name): no separate arrow on STALE")
            XCTAssertEqual(p.secondary, ScreenPresentation.Line(text: c.lines[1], struck: true), c.name)
            XCTAssertTrue(c.lines[1].hasPrefix("last: "), c.name)
            XCTAssertEqual(p.age, c.lines[2], c.name)
            XCTAssertEqual(p.chip, ScreenPresentation.Chip(word: "STALE - DO NOT TRUST", tone: .stale))
        }
    }

    func testNoDataVectorsGiveNoNumber() throws {
        for c in try cases(.noData) {
            let p = c.presentation
            XCTAssertEqual(p.banner, .noData, c.name)
            XCTAssertEqual(p.hero, .none, c.name)
            XCTAssertNil(p.secondary, c.name)
            XCTAssertNil(p.age, c.name)
            XCTAssertEqual(p.context, Array(c.lines.dropFirst()), c.name)
            let shown = ([p.chip.word] + p.context).joined(separator: " ")
            XCTAssertFalse(shown.contains(where: \.isNumber), "\(c.name): no digit anywhere")
        }
    }

    func testSentinelVectorsGiveAWordHero() throws {
        let sentinels = try cases().filter(\.isSentinel)
        XCTAssertEqual(Set(sentinels.map(\.name)), ["sensor_low_sentinel", "sensor_high_sentinel"])
        for c in sentinels {
            XCTAssertEqual(c.presentation.hero, .word(c.lines[1]), c.name)
            XCTAssertNil(c.presentation.hero.arrowSymbol, c.name)
        }
    }

    func testTheLabelIsSpokenText() throws {
        for c in try cases() {
            XCTAssertEqual(c.presentation.accessibilityLabel,
                           spokenText(status: c.status, error: c.vector.error != nil), c.name)
        }
        let p = ScreenPresentation(status: classify(GlucoseReading(mgdl: 112, timestampMs: nowMs - 3 * 60_000,
                                                                   trend: .flat),
                                                    nowMs: nowMs, thresholds: .defaults))
        XCTAssertEqual(p.accessibilityLabel, "In range. 112 milligrams per deciliter, steady. 3 minutes ago.")
    }

    /// The panel preview draws `lines`, and the glance draws each of them once, in order.
    func testEveryVectorLineIsShownOnceInOrder() throws {
        for c in try cases() {
            let p = c.presentation
            XCTAssertEqual(p.lines, c.lines, "\(c.name): the panel preview is renderLines exactly")
            var shown = [p.chip.word]
            switch p.hero {
            case .number(let digits, let arrow, let unit): shown.append("\(digits) \(unit) \(arrow)")
            case .word(let word): shown.append(word)
            case .none: break
            }
            if let secondary = p.secondary { shown.append(secondary.text) }
            if let age = p.age { shown.append(age) }
            shown += p.context
            XCTAssertEqual(shown, c.lines, c.name)
        }
    }

    func testShapesAndTokensFollowTheBrandStatusTable() throws {
        let tokens = try JSONDecoder().decode(Tokens.self, from: repoFile("assets/brand/tokens.json"))
        let banner: [String: ScreenPresentation.Banner] = [
            "plain": .none, "rule": .none, "inverse": .urgent, "stale": .stale, "dashed": .noData,
        ]
        for (headline, token) in tokens.status {
            let p = ScreenPresentation(lines: [token.word, "x"], accessibilityLabel: "")
            XCTAssertEqual(p.chip.word, token.word, headline)
            XCTAssertEqual(p.banner, banner[token.treatment], headline)
            XCTAssertEqual(p.chip.tone.colorToken, token.color, headline)
            XCTAssertEqual(p.chip.tone.chipToken, token.chip, headline)
        }
        let unknown = ScreenPresentation(lines: ["SOMETHING NEW", "120 mg/dL ->", "1 min ago"],
                                         accessibilityLabel: "")
        XCTAssertEqual(unknown.banner, banner[tokens.unknown_headline.treatment])
        XCTAssertEqual(unknown.chip.tone.colorToken, tokens.unknown_headline.color)
        XCTAssertEqual(unknown.chip.tone.chipToken, tokens.unknown_headline.chip)
        XCTAssertEqual(Set(ScreenPresentation.Tone.allCases.map(\.colorToken)),
                       Set(tokens.status.values.map(\.color)))
    }

    // MARK: Beyond the vectors

    func testAnUnknownHeadlineGetsTheMostCautiousShape() {
        for headline in ["", "STALE", "stale - do not trust", "IN RANGE ", "URGENT"] {
            let p = ScreenPresentation(lines: [headline, "120 mg/dL ->", "1 min ago"], accessibilityLabel: "")
            XCTAssertEqual(p.banner, .noData, "\(headline)")
            XCTAssertEqual(p.hero, .none, "\(headline): an unplanned headline never shows a number")
            XCTAssertEqual(p.context, ["120 mg/dL ->", "1 min ago"], "\(headline)")
        }
        let empty = ScreenPresentation(lines: [], accessibilityLabel: "")
        XCTAssertEqual(empty.banner, .noData)
        XCTAssertEqual(empty.hero, .none)
    }

    func testAValueLineThatIsNotAPlainNumberIsShownVerbatim() {
        for value in ["112 mg/dL", "112 mg/dL ~>", "112 mmol/L ->", "1l2 mg/dL ->", " mg/dL ->",
                      "112  mg/dL ->", "١١٢ mg/dL ->"] {
            let p = ScreenPresentation(lines: ["IN RANGE", value, "1 min ago"], accessibilityLabel: "")
            XCTAssertEqual(p.hero, .word(value), value)
        }
        let p = ScreenPresentation(lines: ["HIGH", "250 mg/dL ^^", "2 min ago"], accessibilityLabel: "")
        XCTAssertEqual(p.hero, .number(digits: "250", arrow: "^^", unit: "mg/dL"))
        XCTAssertEqual(p.hero.arrowSymbol, "⇈")
    }

    func testAShortFreshScreenKeepsWhatItHas() {
        let p = ScreenPresentation(lines: ["LOW", "65 mg/dL v"], accessibilityLabel: "")
        XCTAssertEqual(p.hero, .number(digits: "65", arrow: "v", unit: "mg/dL"))
        XCTAssertNil(p.age)
        XCTAssertEqual(p.context, [])
        let headlineOnly = ScreenPresentation(lines: ["STALE - DO NOT TRUST"], accessibilityLabel: "")
        XCTAssertNil(headlineOnly.secondary)
        XCTAssertNil(headlineOnly.age)
    }

    func testUnreachableIsKeptAsContext() {
        let reading = GlucoseReading(mgdl: 101, timestampMs: nowMs - 7 * 60_000, trend: .flat)
        let fresh = ScreenPresentation(status: classify(reading, nowMs: nowMs, thresholds: .defaults),
                                       fetchError: true)
        XCTAssertEqual(fresh.context, ["Nightscout unreachable"])
        XCTAssertTrue(fresh.accessibilityLabel.hasSuffix(" Nightscout unreachable."))
        let stale = ScreenPresentation(status: classify(reading, nowMs: nowMs + 60 * 60_000,
                                                        thresholds: .defaults), fetchError: true)
        XCTAssertEqual(stale.context, ["Nightscout unreachable"])
        XCTAssertEqual(stale.lines.count, maxLines)
    }

    // MARK: Captions

    func testCaptionsAreAbsoluteTwentyFourHourTimes() throws {
        let utc = try XCTUnwrap(TimeZone(identifier: "UTC"))
        let noon = Date(timeIntervalSince1970: Double(nowMs) / 1000)
        XCTAssertEqual(clockText(noon, timeZone: utc), "12:00")
        XCTAssertEqual(checkedCaption(noon, timeZone: utc), "checked 12:00")
        XCTAssertEqual(offlineCaption(since: noon, timeZone: utc), "Nightscout unreachable since 12:00")

        let minusFour = try XCTUnwrap(TimeZone(secondsFromGMT: -4 * 3600))
        let later = noon.addingTimeInterval(13 * 3600 + 5 * 60 + 59)
        XCTAssertEqual(clockText(later, timeZone: minusFour), "21:05", "local, padded, seconds dropped")
        XCTAssertEqual(clockText(noon.addingTimeInterval(12 * 3600 + 3 * 60), timeZone: utc), "00:03")
    }

    func testTheCheckingCaptionIsStaticText() {
        XCTAssertEqual(checkingCaption, "checking Nightscout...")
    }
}

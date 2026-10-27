// FR-019 (proposed) / HAZ-015 (proposed): a glance timeline shows, at every
// moment, exactly what the rules show at that moment. Its STALE frame is
// scheduled at the first stale millisecond, STALE keeps aging once a minute,
// and the frame left up when the timeline runs out is STALE or NO DATA, so a
// widget the system stops refreshing can never keep a fresh-looking number.

import Foundation
import XCTest
@testable import LightkeeperCore

final class GlanceTimelineTests: XCTestCase {
    /// 2026-10-18T12:00:00Z, the same fixed clock the other suites use.
    let nowMs: Int64 = 1_792_324_800_000
    let minute: Int64 = 60_000
    /// Clock offsets from each vector's own time. Sampling every second from
    /// now + 0 lands on whole-minute ages; from now + 1 it lands on the first
    /// STALE millisecond; from now + 999 on the last millisecond before a
    /// boundary.
    let offsets: [Int64] = [-60_000, -1, 0, 1, 999, 30_000, 59_999]
    let unreachable = "Nightscout unreachable"

    // The subset of spec/display_vectors.json a timeline needs.
    struct Entry: Decodable {
        let type: String?
        let sgv: Double?
        let direction: String?
    }
    struct CustomThresholds: Decodable {
        let urgent_low: Int
        let low: Int
        let high: Int
        let urgent_high: Int
        let stale_after_minutes: Int
    }
    /// An item of a multi-entry case; those cases are skipped here.
    struct Item: Decodable {
        let entry: Entry?
    }
    struct Vector: Decodable {
        let name: String
        let entry: Entry?
        let minutes_ago: Int?
        let seconds_ago: Int?
        let entries: [Item]?
        let thresholds: CustomThresholds?
        let error: String?
    }
    struct Spec: Decodable {
        let spec_version: Int
        let cases: [Vector]
    }

    /// A single-entry vector as timeline input: the reading the app would
    /// hold after parsing it at `nowMs`, or nil if the entry is rejected.
    struct Case {
        let name: String
        let reading: GlucoseReading?
        let thresholds: Thresholds
        let fetchError: Bool
    }

    func loadCases() throws -> [Case] {
        var url = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
        while !FileManager.default.fileExists(atPath: url.appendingPathComponent("spec").path),
              url.path != "/" {
            url.deleteLastPathComponent()
        }
        let path = url.appendingPathComponent("spec/display_vectors.json")
        let spec = try JSONDecoder().decode(Spec.self, from: Data(contentsOf: path))
        XCTAssertEqual(spec.spec_version, 1, "bump this assertion when an existing vector changes")

        var cases: [Case] = []
        for v in spec.cases where v.entries == nil {
            var reading: GlucoseReading?
            if let e = v.entry {
                let ageMs = v.seconds_ago.map { Int64($0) * 1000 }
                    ?? Int64(v.minutes_ago ?? 0) * minute
                var raw: [String: Any] = ["date": Double(nowMs - ageMs)]
                if let t = e.type { raw["type"] = t }
                if let s = e.sgv { raw["sgv"] = s }
                if let d = e.direction { raw["direction"] = d }
                reading = parseEntries([raw]).first
            }
            var thresholds = Thresholds.defaults
            if let c = v.thresholds {
                thresholds = try Thresholds(urgentLow: c.urgent_low, low: c.low, high: c.high,
                                            urgentHigh: c.urgent_high,
                                            staleAfterMs: Int64(c.stale_after_minutes) * minute)
            }
            cases.append(Case(name: v.name, reading: reading, thresholds: thresholds,
                              fetchError: v.error != nil))
        }
        XCTAssertGreaterThan(cases.count, 25)
        XCTAssertTrue(cases.contains { $0.reading == nil }, "NO DATA vectors are covered")
        XCTAssertTrue(cases.contains { $0.thresholds != .defaults }, "custom limits are covered")
        XCTAssertTrue(cases.contains { $0.fetchError }, "fetch errors are covered")
        return cases
    }

    /// One timeline per vector and clock offset.
    struct Run {
        let label: String
        let c: Case
        let nowMs: Int64
        let timeline: [GlanceEntry]
    }

    func runs(maxMinutes: Int = 120, fetchError: Bool? = nil) throws -> [Run] {
        try loadCases().flatMap { c in
            offsets.map { offset in
                let now = nowMs + offset
                let timeline = glanceTimeline(lastGood: c.reading,
                                              fetchError: fetchError ?? c.fetchError,
                                              nowMs: now, thresholds: c.thresholds,
                                              maxMinutes: maxMinutes)
                return Run(label: "\(c.name) at now\(offset >= 0 ? "+" : "")\(offset) ms",
                           c: c, nowMs: now, timeline: timeline)
            }
        }
    }

    /// What every other display shows at `t`.
    func expected(_ reading: GlucoseReading?, at t: Int64, _ thresholds: Thresholds,
                  fetchError: Bool) -> (level: Level, lines: [String]) {
        let status = classify(reading, nowMs: t, thresholds: thresholds)
        return (status.level, renderLines(status, fetchError: fetchError))
    }

    func reading(agedMs ageMs: Int64, at now: Int64, mgdl: Int = 120) -> GlucoseReading {
        GlucoseReading(mgdl: mgdl, timestampMs: now - ageMs, trend: .flat)
    }

    /// The age line of a STALE frame, as a number of minutes.
    func staleMinutes(_ entry: GlanceEntry) -> Int? {
        guard entry.level == .stale, entry.lines.count > 2 else { return nil }
        return Int(entry.lines[2].replacingOccurrences(of: " min ago", with: ""))
    }

    /// Each frame is what the rules show at its date; the first is at now and
    /// the dates strictly increase.
    func assertEntriesMatchRender(_ run: Run) {
        let timeline = run.timeline
        XCTAssertEqual(timeline.first?.dateMs, run.nowMs, "\(run.label): first frame is now")
        for (i, entry) in timeline.enumerated() {
            let want = expected(run.c.reading, at: entry.dateMs, run.c.thresholds,
                                fetchError: run.c.fetchError)
            XCTAssertEqual(entry.level, want.level, "\(run.label): frame \(i) level")
            XCTAssertEqual(entry.lines, want.lines, "\(run.label): frame \(i) lines")
            if i > 0 {
                XCTAssertGreaterThan(entry.dateMs, timeline[i - 1].dateMs,
                                     "\(run.label): dates strictly increase")
            }
        }
    }

    /// Each frame starts on the very millisecond the rules change their
    /// answer: one millisecond earlier the previous frame is still exact, and
    /// no frame repeats the one before it.
    func assertEntriesStartAtChanges(_ run: Run) {
        let timeline = run.timeline
        for i in timeline.indices.dropFirst() {
            let before = expected(run.c.reading, at: timeline[i].dateMs - 1, run.c.thresholds,
                                  fetchError: run.c.fetchError)
            XCTAssertEqual(before.level, timeline[i - 1].level, "\(run.label): frame \(i)")
            XCTAssertEqual(before.lines, timeline[i - 1].lines, "\(run.label): frame \(i)")
            XCTAssertNotEqual(timeline[i].lines, timeline[i - 1].lines,
                              "\(run.label): frame \(i) changes something")
        }
    }

    /// Sampled every second from now to the last frame, the frame in effect
    /// (the last one dated at or before the sample) is what the rules show
    /// then. Returns the number of samples.
    @discardableResult
    func assertEverySecondMatches(_ run: Run) -> Int {
        let timeline = run.timeline
        guard let last = timeline.last else {
            XCTFail("\(run.label): empty timeline")
            return 0
        }
        var samples = 0
        var current = 0
        var t = run.nowMs
        while t <= last.dateMs {
            while current + 1 < timeline.count, timeline[current + 1].dateMs <= t {
                current += 1
            }
            let want = expected(run.c.reading, at: t, run.c.thresholds,
                                fetchError: run.c.fetchError)
            if timeline[current].level != want.level || timeline[current].lines != want.lines {
                XCTFail("\(run.label): at now+\(t - run.nowMs) ms the frame shows "
                        + "\(timeline[current].lines) but the rules show \(want.lines)")
                break
            }
            samples += 1
            t += 1000
        }
        return samples
    }

    // MARK: - Every frame is the rules' own output

    func testFR019EntryLinesEqualRenderAtEntryTime() throws {
        for run in try runs() {
            assertEntriesMatchRender(run)
        }
    }

    func testFR019EntriesStartExactlyWhenTheLinesChange() throws {
        for run in try runs() {
            assertEntriesStartAtChanges(run)
        }
    }

    /// The safety property: whatever second the system draws the widget, the
    /// frame in effect is what the rules say at that second, so no fresh frame
    /// is ever in effect after the data is stale. maxMinutes 0 covers the
    /// schedule that stops at the first STALE millisecond.
    func testFR019EverySecondMatchesClassify() throws {
        var samples = 0
        for maxMinutes in [120, 0] {
            for run in try runs(maxMinutes: maxMinutes) {
                samples += assertEverySecondMatches(run)
            }
        }
        XCTAssertGreaterThan(samples, 500_000, "the sweep really ran")
    }

    /// Stale limits that are not whole minutes, including one whose first
    /// STALE millisecond is also a minute boundary, keep every property.
    func testFR019OddStaleLimitsStayExact() throws {
        for limitMs: Int64 in [1, 999, 59_999, 60_000, 60_001, 90_500, 899_999, 3_600_000] {
            let thresholds = try Thresholds(staleAfterMs: limitMs)
            for ageMs: Int64 in [-2 * minute - 500, -1, 0, 30_000, 59_999, 60_000, 3 * minute] {
                for fetchError in [false, true] {
                    let c = Case(name: "limit \(limitMs) ms, age \(ageMs) ms",
                                 reading: reading(agedMs: ageMs, at: nowMs),
                                 thresholds: thresholds, fetchError: fetchError)
                    for maxMinutes in [0, 120] {
                        let run = Run(label: "\(c.name), max \(maxMinutes)", c: c, nowMs: nowMs,
                                      timeline: glanceTimeline(lastGood: c.reading,
                                                               fetchError: fetchError,
                                                               nowMs: nowMs, thresholds: thresholds,
                                                               maxMinutes: maxMinutes))
                        assertEntriesMatchRender(run)
                        assertEntriesStartAtChanges(run)
                        assertEverySecondMatches(run)
                        XCTAssertEqual(run.timeline.last?.level, .stale, run.label)
                        XCTAssertLessThanOrEqual(run.timeline.count,
                                                 max(maxMinutes, Int(limitMs / minute) + 1) + 3,
                                                 run.label)
                    }
                }
            }
        }
    }

    // MARK: - STALE is scheduled, on time, and keeps aging

    func testFR019EntryAtFirstStaleMillisecond() throws {
        var checked = 0
        for run in try runs() where run.timeline.first?.level != .stale {
            guard let reading = run.c.reading else { continue }
            let firstStale = reading.timestampMs + run.c.thresholds.staleAfterMs + 1
            let stale = try XCTUnwrap(run.timeline.first { $0.level == .stale }, run.label)
            XCTAssertEqual(stale.dateMs, firstStale, "\(run.label): STALE on the first stale ms")
            let before = classify(reading, nowMs: stale.dateMs - 1, thresholds: run.c.thresholds)
            XCTAssertNotEqual(before.level, .stale, "\(run.label): one ms earlier is not STALE")
            checked += 1
        }
        XCTAssertGreaterThan(checked, 100)

        // Default limit: "15 min ago" is still fresh for exactly one millisecond.
        let r = reading(agedMs: 3 * minute, at: nowMs)
        let timeline = glanceTimeline(lastGood: r, fetchError: false, nowMs: nowMs,
                                      thresholds: .defaults)
        let i = try XCTUnwrap(timeline.firstIndex { $0.level == .stale })
        guard i > 0 else { return XCTFail("STALE at once: \(timeline[i])") }
        XCTAssertEqual(timeline[i].dateMs, r.timestampMs + 15 * minute + 1)
        XCTAssertEqual(timeline[i].lines, ["STALE - DO NOT TRUST", "last: 120 mg/dL ->",
                                           "15 min ago", "Confirm on primary device"])
        XCTAssertEqual(timeline[i - 1].dateMs, r.timestampMs + 15 * minute)
        XCTAssertEqual(timeline[i - 1].lines, ["IN RANGE", "120 mg/dL ->", "15 min ago"])
    }

    func testFR019StaleKeepsAgingPerMinute() throws {
        // Fresh now, then STALE from 15 minutes, aging to the 120-minute end.
        let r = reading(agedMs: 3 * minute, at: nowMs)
        let timeline = glanceTimeline(lastGood: r, fetchError: false, nowMs: nowMs,
                                      thresholds: .defaults)
        let stale = timeline.filter { $0.level == .stale }
        XCTAssertEqual(stale.compactMap(staleMinutes), Array(15...120))
        for (earlier, later) in zip(stale.dropFirst(), stale.dropFirst(2)) {
            XCTAssertEqual(later.dateMs - earlier.dateMs, minute, "one STALE frame a minute")
        }
        XCTAssertEqual(stale.dropFirst().first?.dateMs, r.timestampMs + 16 * minute)
        XCTAssertEqual(timeline.last?.dateMs, r.timestampMs + 120 * minute)
        XCTAssertFalse(timeline.drop { $0.level != .stale }.contains { $0.level != .stale },
                       "once STALE, never fresh again")

        // Already STALE now: it keeps aging from its current age.
        let old = reading(agedMs: 40 * minute + 30_000, at: nowMs)
        let aging = glanceTimeline(lastGood: old, fetchError: false, nowMs: nowMs,
                                   thresholds: .defaults)
        XCTAssertEqual(aging.compactMap(staleMinutes), Array(40...120))
        XCTAssertEqual(aging.count, 81)
        XCTAssertTrue(aging.allSatisfy { $0.level == .stale })
    }

    func testFR019LastEntryIsStaleOrNoData() throws {
        for maxMinutes in [-5, 0, 1, 14, 15, 16, 60, 120, 240] {
            for run in try runs(maxMinutes: maxMinutes) {
                let last = try XCTUnwrap(run.timeline.last, run.label)
                XCTAssertEqual(last.level, run.c.reading == nil ? .noData : .stale,
                               "\(run.label), maxMinutes \(maxMinutes)")
            }
        }
    }

    // MARK: - Clock skew, custom limits, fetch errors, no data

    func testFR019FutureDatedCoversBothTransitions() throws {
        // Ten minutes ahead of the clock (vector future_dated): STALE now,
        // trusted from 2 minutes ahead, then aging and STALE again.
        let r = reading(agedMs: -10 * minute, at: nowMs)
        let timeline = glanceTimeline(lastGood: r, fetchError: false, nowMs: nowMs,
                                      thresholds: .defaults)
        guard timeline.count > 3 else { return XCTFail("too few frames: \(timeline)") }
        XCTAssertEqual(timeline[0], GlanceEntry(
            dateMs: nowMs, level: .stale,
            lines: ["STALE - DO NOT TRUST", "last: 120 mg/dL ->", "time is in the future",
                    "Confirm on primary device"]))
        XCTAssertEqual(timeline[1], GlanceEntry(dateMs: r.timestampMs - 2 * minute, level: .inRange,
                                                lines: ["IN RANGE", "120 mg/dL ->", "just now"]))
        XCTAssertEqual(classify(r, nowMs: timeline[1].dateMs - 1, thresholds: .defaults).level,
                       .stale, "one ms earlier the skew is still too large")
        XCTAssertEqual(timeline[2].dateMs, r.timestampMs + minute)
        XCTAssertEqual(timeline[2].lines, ["IN RANGE", "120 mg/dL ->", "1 min ago"])
        let restale = try XCTUnwrap(timeline.dropFirst().first { $0.level == .stale })
        XCTAssertEqual(restale.dateMs, r.timestampMs + 15 * minute + 1)
        XCTAssertEqual(timeline.last?.dateMs, r.timestampMs + 120 * minute)
        XCTAssertEqual(reloadAfterMs(for: timeline), nowMs + glanceReloadIntervalMs,
                       "STALE from the first frame: ask one reading interval later")

        // Exactly 2 minutes ahead is trusted at once; 1 ms more is trusted 1 ms later.
        let edge = glanceTimeline(lastGood: reading(agedMs: -2 * minute, at: nowMs),
                                  fetchError: false, nowMs: nowMs, thresholds: .defaults)
        let past = glanceTimeline(lastGood: reading(agedMs: -2 * minute - 1, at: nowMs),
                                  fetchError: false, nowMs: nowMs, thresholds: .defaults)
        guard edge.count > 1, past.count > 1 else { return XCTFail("too few frames") }
        XCTAssertEqual(edge[0].level, .inRange)
        XCTAssertEqual(edge[1].dateMs, nowMs + 3 * minute, "next change is \"1 min ago\"")
        XCTAssertEqual(past[0].level, .stale)
        XCTAssertEqual(past[1].dateMs, nowMs + 1)
        XCTAssertEqual(past[1].level, .inRange)
    }

    func testFR019CustomStaleAfterTenMinutes() throws {
        let thresholds = try Thresholds(urgentLow: 60, low: 80, high: 160, urgentHigh: 220,
                                        staleAfterMs: 10 * minute)
        let r = reading(agedMs: 3 * minute, at: nowMs)
        let timeline = glanceTimeline(lastGood: r, fetchError: false, nowMs: nowMs,
                                      thresholds: thresholds)
        let i = try XCTUnwrap(timeline.firstIndex { $0.level == .stale })
        guard i > 0 else { return XCTFail("STALE at once: \(timeline[i])") }
        XCTAssertEqual(timeline[i - 1].dateMs, r.timestampMs + 10 * minute)
        XCTAssertEqual(timeline[i - 1].lines, ["IN RANGE", "120 mg/dL ->", "10 min ago"])
        XCTAssertEqual(timeline[i].dateMs, r.timestampMs + 10 * minute + 1)
        XCTAssertEqual(timeline.filter { $0.level == .stale }.compactMap(staleMinutes),
                       Array(10...120))

        // The iOS settings allow up to 60 minutes; the schedule still ends STALE
        // when the limit outlasts maxMinutes.
        let hour = try Thresholds(staleAfterMs: 60 * minute)
        for maxMinutes in [-1, 0, 30, 59, 60] {
            let long = glanceTimeline(lastGood: r, fetchError: false, nowMs: nowMs,
                                      thresholds: hour, maxMinutes: maxMinutes)
            XCTAssertEqual(long.last?.dateMs, r.timestampMs + 60 * minute + 1, "\(maxMinutes)")
            XCTAssertEqual(long.last.flatMap(staleMinutes), 60)
            XCTAssertEqual(long.filter { $0.level == .stale }.count, 1)
            XCTAssertLessThanOrEqual(long.count, 60 + 3)
        }
    }

    func testFR019FetchErrorOnEveryEntry() throws {
        let failing = try runs(fetchError: true)
        let working = try runs(fetchError: false)
        XCTAssertEqual(failing.count, working.count)
        for (bad, good) in zip(failing, working) {
            XCTAssertEqual(bad.timeline.map(\.dateMs), good.timeline.map(\.dateMs),
                           "\(bad.label): a fetch error never moves a frame")
            for (b, g) in zip(bad.timeline, good.timeline) {
                XCTAssertEqual(b.lines.last, unreachable, bad.label)
                XCTAssertLessThanOrEqual(b.lines.count, maxLines, bad.label)
                XCTAssertEqual(b.lines, renderLines(classify(bad.c.reading, nowMs: b.dateMs,
                                                             thresholds: bad.c.thresholds),
                                                    fetchError: true), bad.label)
                XCTAssertFalse(g.lines.contains(unreachable), good.label)
            }
        }

        // The first frame after a failed fetch is what the app shows (FR-005).
        struct Down: Error {}
        let lastGood = classify(reading(agedMs: 2 * minute, at: nowMs), nowMs: nowMs,
                                thresholds: .defaults)
        for later in [5 * minute, 30 * minute] {
            let app = currentStatus(entries: .failure(Down()), nowMs: nowMs + later,
                                    thresholds: .defaults, lastGood: lastGood)
            let timeline = glanceTimeline(lastGood: lastGood.reading, fetchError: true,
                                          nowMs: nowMs + later, thresholds: .defaults)
            XCTAssertEqual(timeline.first?.level, app.status.level)
            XCTAssertEqual(timeline.first?.lines,
                           renderLines(app.status, fetchError: app.fetchError))
        }
    }

    func testFR019NoReadingGivesOneNoDataEntry() {
        let noData = ["NO DATA", "Check sensor and phone", "Confirm on primary device"]
        for maxMinutes in [-1, 0, 120, Int.max] {
            XCTAssertEqual(glanceTimeline(lastGood: nil, fetchError: false, nowMs: nowMs,
                                          thresholds: .defaults, maxMinutes: maxMinutes),
                           [GlanceEntry(dateMs: nowMs, level: .noData, lines: noData)])
        }
        let failed = glanceTimeline(lastGood: nil, fetchError: true, nowMs: nowMs,
                                    thresholds: .defaults)
        XCTAssertEqual(failed, [GlanceEntry(dateMs: nowMs, level: .noData,
                                            lines: noData + [unreachable])])
        XCTAssertEqual(reloadAfterMs(for: failed), nowMs + glanceReloadIntervalMs,
                       "only a fetch changes it: ask one reading interval later")
    }

    // MARK: - Bounds and the reload hint

    func testFR019EntryCountBounded() throws {
        for maxMinutes in [0, 1, 15, 60, 120, 240] {
            for run in try runs(maxMinutes: maxMinutes) {
                XCTAssertLessThanOrEqual(run.timeline.count, maxMinutes + 20,
                                         "\(run.label), maxMinutes \(maxMinutes)")
            }
        }
        // A reading older than the schedule is one STALE frame.
        let old = glanceTimeline(lastGood: reading(agedMs: 180 * minute, at: nowMs),
                                 fetchError: false, nowMs: nowMs, thresholds: .defaults)
        XCTAssertEqual(old.count, 1)
        XCTAssertEqual(old.first.flatMap(staleMinutes), 180)
        XCTAssertEqual(reloadAfterMs(for: old), nowMs + glanceReloadIntervalMs)
    }

    /// Absurd inputs neither trap nor build a huge timeline: maxMinutes and the
    /// minute ticks stop at one day, a stale limit no instant can exceed is
    /// never called STALE, by the rules or by the timeline, and no scheduled
    /// instant has an age classify() cannot work out.
    func testFR019HugeLimitsStayBoundedAndNeverTrap() throws {
        let cap = glanceScheduleCapMinutes
        let r = reading(agedMs: 0, at: nowMs)

        // Now, a tick a minute for a day, and the STALE millisecond at 15 minutes.
        let day = glanceTimeline(lastGood: r, fetchError: false, nowMs: nowMs,
                                 thresholds: .defaults, maxMinutes: .max)
        XCTAssertEqual(day.count, cap + 2)
        XCTAssertEqual(day.last?.dateMs, r.timestampMs + Int64(cap) * minute)
        XCTAssertEqual(day.last.flatMap(staleMinutes), cap)

        // A limit beyond the cap: ticks stop at one day, STALE still comes on time.
        let threeDays = Int64(3 * cap) * minute
        let longLimit = try Thresholds(staleAfterMs: threeDays)
        let long = glanceTimeline(lastGood: r, fetchError: false, nowMs: nowMs,
                                  thresholds: longLimit)
        XCTAssertEqual(long.count, cap + 2)
        guard long.count == cap + 2 else { return }
        XCTAssertEqual(long[cap].dateMs, r.timestampMs + Int64(cap) * minute)
        XCTAssertEqual(long[cap].level, .inRange)
        XCTAssertEqual(long.last?.dateMs, r.timestampMs + threeDays + 1)
        XCTAssertEqual(long.last?.level, .stale)

        // A limit no instant can exceed.
        let endless = try Thresholds(staleAfterMs: .max)
        let never = glanceTimeline(lastGood: r, fetchError: false, nowMs: nowMs,
                                   thresholds: endless, maxMinutes: .max)
        XCTAssertEqual(never.count, cap + 1)
        XCTAssertFalse(never.contains { $0.level == .stale })
        let last = try XCTUnwrap(never.last)
        XCTAssertEqual(last.lines, expected(r, at: last.dateMs, endless, fetchError: false).lines)

        // The first STALE instant, and its age, at the end of Int64: a limit
        // that ends exactly on Int64.max (the instant would be one past it), a
        // limit of Int64.max on a reading before 1970 (the instant fits, its
        // age does not), and a first STALE millisecond that is Int64.max itself.
        let ends: [(label: String, readingMs: Int64, now: Int64, limitMs: Int64, stale: Bool)] = [
            ("limit ends on Int64.max", nowMs, nowMs, Int64.max - nowMs, false),
            ("STALE age past Int64.max", -10, 0, .max, false),
            ("first STALE ms is Int64.max", nowMs, nowMs, Int64.max - 1 - nowMs, true),
        ]
        for end in ends {
            let edge = GlucoseReading(mgdl: 120, timestampMs: end.readingMs, trend: .flat)
            let limit = try Thresholds(staleAfterMs: end.limitMs)
            let c = Case(name: end.label, reading: edge, thresholds: limit, fetchError: false)
            let timeline = glanceTimeline(lastGood: edge, fetchError: false, nowMs: end.now,
                                          thresholds: limit, maxMinutes: .max)
            let run = Run(label: end.label, c: c, nowMs: end.now, timeline: timeline)
            XCTAssertEqual(run.timeline.map { $0.level == .stale },
                           [Bool](repeating: false, count: cap + 1) + (end.stale ? [true] : []),
                           "\(end.label): one frame a minute for a day, then STALE if it fits")
            assertEntriesMatchRender(run)
            if end.stale {
                // Past the one-day cap the age lags until STALE (see above), but
                // STALE itself still lands on its first millisecond.
                XCTAssertEqual(run.timeline.last?.dateMs, .max, end.label)
                XCTAssertNotEqual(classify(edge, nowMs: .max - 1, thresholds: limit).level, .stale,
                                  end.label)
            } else {
                assertEntriesStartAtChanges(run)
            }
            XCTAssertEqual(reloadAfterMs(for: run.timeline), end.now + glanceReloadIntervalMs,
                           end.label)
        }

        // Timestamps at the ends of the Int64 range. Near the top, every later
        // instant pins to Int64.max, where the reading is still 10 ms old, so
        // one frame is the whole truth; near the bottom the schedule is normal.
        for (ts, now, count) in [(Int64.max - 10, Int64.max - 5, 1),
                                 (Int64.min + 10, Int64.min + 20, 122)] {
            let edge = GlucoseReading(mgdl: 120, timestampMs: ts, trend: .flat)
            let run = Run(label: "timestamp \(ts)",
                          c: Case(name: "edge", reading: edge, thresholds: .defaults,
                                  fetchError: false),
                          nowMs: now, timeline: glanceTimeline(lastGood: edge, fetchError: false,
                                                               nowMs: now, thresholds: .defaults))
            XCTAssertEqual(run.timeline.first?.lines, ["IN RANGE", "120 mg/dL ->", "just now"])
            XCTAssertEqual(run.timeline.count, count, run.label)
            assertEntriesMatchRender(run)
            assertEntriesStartAtChanges(run)
        }
    }

    /// Follows the reload hint for a day, reloading exactly when it asks, and
    /// counts the reloads. `newest` is the newest reading Nightscout has at t.
    func reloadsInADay(_ newest: (Int64) -> GlucoseReading?) throws -> Int {
        var t = nowMs
        var reloads = 0
        while t < nowMs + 24 * 60 * minute {
            let timeline = glanceTimeline(lastGood: newest(t), fetchError: false, nowMs: t,
                                          thresholds: .defaults)
            let next = try XCTUnwrap(reloadAfterMs(for: timeline))
            XCTAssertGreaterThan(next, t, "the hint is always in the future")
            t = next
            reloads += 1
        }
        return reloads
    }

    /// The reload hint follows Nightscout's reading cadence, not the minute
    /// ticks of the age text: it waits one reading interval, or less only to
    /// try for fresh data the moment the timeline would turn STALE. Asking at
    /// every boundary would be once a minute: the daily budget in an hour.
    func testFR019ReloadAfterFollowsTheReadingCadence() throws {
        let interval = glanceReloadIntervalMs
        XCTAssertEqual(interval, 5 * minute)
        for maxMinutes in [120, 0] {
            for run in try runs(maxMinutes: maxMinutes) {
                let hint = try XCTUnwrap(reloadAfterMs(for: run.timeline), run.label)
                XCTAssertGreaterThan(hint, run.nowMs, run.label)
                XCTAssertLessThanOrEqual(hint, run.nowMs + interval, run.label)
                let turnsStale = run.timeline.indices.dropFirst().first {
                    run.timeline[$0].level == .stale && run.timeline[$0 - 1].level != .stale
                }.map { run.timeline[$0].dateMs }
                XCTAssertLessThanOrEqual(hint, turnsStale ?? .max, "\(run.label): not after STALE")
                XCTAssertTrue(hint == run.nowMs + interval || hint == turnsStale,
                              "\(run.label): no sooner than it needs to be")
            }
        }
        XCTAssertNil(reloadAfterMs(for: []))

        // A fresh reading 3:20 old asks in 5 minutes, not at its next boundary.
        let r = reading(agedMs: 3 * minute + 20_000, at: nowMs)
        let timeline = glanceTimeline(lastGood: r, fetchError: false, nowMs: nowMs,
                                      thresholds: .defaults)
        XCTAssertEqual(timeline.dropFirst().first?.dateMs, nowMs + 40_000)
        XCTAssertEqual(reloadAfterMs(for: timeline), nowMs + interval)

        // A reading 12 minutes old asks on the millisecond it turns STALE.
        let late = reading(agedMs: 12 * minute, at: nowMs)
        let turning = glanceTimeline(lastGood: late, fetchError: false, nowMs: nowMs,
                                     thresholds: .defaults)
        XCTAssertEqual(reloadAfterMs(for: turning), late.timestampMs + 15 * minute + 1)

        // A day of following the hint: one reload per reading interval whether
        // readings keep coming, stop, or never existed (each boundary: 1440).
        let perDay = 24 * 60 / 5
        let start = nowMs - 3 * minute
        let everyFive = try reloadsInADay { t in reading(agedMs: (t - start) % interval, at: t) }
        XCTAssertEqual(everyFive, perDay, "readings every 5 minutes")
        let stopped = try reloadsInADay { _ in reading(agedMs: 3 * minute, at: nowMs) }
        XCTAssertEqual(stopped, perDay + 1, "readings stop: one extra, as it turns STALE")
        XCTAssertEqual(try reloadsInADay { _ in nil }, perDay, "no data at all")
    }
}

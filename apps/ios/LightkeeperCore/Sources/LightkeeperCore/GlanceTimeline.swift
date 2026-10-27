// The glance timeline: every frame a widget, a StandBy card, or a Live
// Activity will need, worked out in advance with the same rules as every
// other display, so the frames turn STALE on time even if nothing runs again.
//
// Why the frames are scheduled ahead. WidgetKit, not the app, decides when a
// widget's provider runs, and its daily refresh budget (roughly 40 to 70
// reloads) can leave one frame on screen for hours. A frame drawn as "3 min
// ago" would go on saying so long after the data went stale (proposed
// HAZ-015). So the provider hands over every future frame at once:
// - one at now;
// - one at each minute boundary of the reading's age;
// - one at the first millisecond classify() calls the reading STALE (age
//   greater than the stale limit): exactly then, not a second later;
// - for a future-dated reading, one at the first millisecond its skew is
//   2 minutes or less;
// and STALE then carries on once a minute until the reading is maxMinutes
// old, so a frozen widget shows a growing age instead of "15 min ago". The
// STALE frames are in the timeline from the start, so they appear on time
// whether or not the provider ever runs again, and the last frame (the one
// left showing when the timeline runs out) is always STALE or NO DATA. The
// only exception is a stale limit or timestamp so close to the end of Int64
// that classify() never says STALE at any later instant; nothing the parser
// or the settings accept comes near one.
//
// Every frame's lines come from classify() and renderLines(), so there is no
// new screen text. Pure: the time comes in as nowMs, and nothing here reads
// the clock or the network. Nothing traps unless classify() itself would at
// nowMs: every later instant the timeline schedules has an age classify()
// can work out, even at the ends of Int64.
//
// WidgetKit contract for the extension (not built yet; it needs D10, Apple
// signing and App Groups):
// - One TimelineEntry per GlanceEntry, in order, dated dateMs, drawing
//   `lines` verbatim. Never Text(date, style: .relative) or .timer: the
//   system's wording would not match the vectors' "N min ago", and it keeps
//   counting on its own instead of following these frames.
// - Timeline policy .atEnd is always safe: if WidgetKit never reloads, the
//   frame that stays up is the last one, and it says DO NOT TRUST (or NO
//   DATA).
// - To pick up a new reading sooner, use .after(reloadAfterMs(for:)) (.atEnd
//   only for an empty timeline, which glanceTimeline never returns). The hint
//   follows the data, not the age text: one reading interval (5 minutes)
//   after now, or sooner if the timeline turns STALE before then, the moment
//   a fresh reading matters most. WidgetKit treats the date as a request
//   within its budget and may reload much later; the frames already cover
//   every moment in between, so a late reload costs freshness, never honesty.
// - Never ask for a reload at every frame boundary. That is once a minute,
//   and it spends the daily budget in about an hour; new readings then stop
//   reaching the widget for the rest of the day, and it sits on STALE frames
//   that are correct but needless. A STALE that shows for hours every day
//   teaches people to ignore STALE. The 5-minute interval is a starting
//   point, to be measured on a device with the extension.
// - The app should also call WidgetCenter.shared.reloadAllTimelines() when
//   it gets a new reading and after a settings save, so frames built with
//   old data or old thresholds are replaced without waiting for the hint.
// - Whether a STALE widget shows the struck "last:" line or no number is
//   still to be decided; either way the text comes from `lines`.
// - A Live Activity has no timeline of its own: the first STALE entry's date
//   is the staleDate to give ActivityKit.

/// One frame of a glance surface: what to show from `dateMs` until the next
/// entry's date, or for as long as the system keeps it up if it is the last.
///
/// Only `glanceTimeline` makes these, so every frame carries vector text.
public struct GlanceEntry: Equatable, Sendable {
    /// When this frame takes effect, in Unix milliseconds.
    public let dateMs: Int64
    public let level: Level
    /// Exactly `renderLines(classify(reading, nowMs: dateMs, ...), fetchError:)`.
    public let lines: [String]
}

/// The longest schedule a timeline holds, in minutes after the reading: one
/// day, so a widget's memory stays bounded whatever maxMinutes or stale limit
/// it is handed. The iOS settings cap the stale limit at 60 minutes.
let glanceScheduleCapMinutes = 24 * 60

private let msPerMinute: Int64 = 60_000

/// The longest wait the reload hint asks for: one CGM reading interval.
/// Nightscout gets about one reading every 5 minutes, so asking sooner
/// mostly finds nothing new and spends WidgetKit's daily budget for nothing.
let glanceReloadIntervalMs: Int64 = 5 * msPerMinute

/// `a + b`, pinned to the Int64 range instead of trapping.
private func clampedSum(_ a: Int64, _ b: Int64) -> Int64 {
    let (sum, overflow) = a.addingReportingOverflow(b)
    if !overflow { return sum }
    return b > 0 ? .max : .min
}

/// Every instant after `nowMs` at which the rendered lines can change, in order.
///
/// The lines depend on time only through the age text, which changes at each
/// whole minute after the reading, and the level, which changes where
/// classify() changes its mind about staleness. Instants where nothing
/// changes are dropped by the caller.
private func boundaries(of reading: GlucoseReading, after nowMs: Int64,
                        thresholds: Thresholds, maxMinutes: Int) -> [Int64] {
    let readingMs = reading.timestampMs
    // classify() calls a reading STALE once its age is greater than the stale
    // limit: from age limit + 1, which is the instant reading + limit + 1. If
    // that age or that instant is past the end of Int64, it never comes, and
    // classify() could not work out the age there, so it is not scheduled.
    let staleAgeMs: Int64? = thresholds.staleAfterMs < .max ? thresholds.staleAfterMs + 1 : nil
    let firstStaleMs = staleAgeMs.flatMap { readingMs <= Int64.max - $0 ? readingMs + $0 : nil }
    // A future-dated reading is trusted again once it is no more than
    // maxFutureSkewMs ahead of the clock.
    var instants = [clampedSum(readingMs, -maxFutureSkewMs)]
    if let firstStaleMs { instants.append(firstStaleMs) }

    // Minute ticks run until the reading is maxMinutes old, and on to the
    // first STALE millisecond if that comes later, so the schedule always ends
    // STALE. Past the cap there are no more ticks, but the STALE instant above
    // is kept: with a limit longer than a day the age then lags until STALE,
    // which is still better than a fresh frame that never ends.
    let minutes = Int64(min(max(maxMinutes, 0), glanceScheduleCapMinutes))
    let lastTickMs = max(clampedSum(readingMs, minutes * msPerMinute), firstStaleMs ?? .min)
    for minute in 1...Int64(glanceScheduleCapMinutes) {
        let tickMs = clampedSum(readingMs, minute * msPerMinute)
        if tickMs > lastTickMs { break }
        instants.append(tickMs)
    }
    return instants.filter { $0 > nowMs }.sorted()
}

/// Every frame from `nowMs` on, each one exactly what the rules show at its date.
///
/// - Parameters:
///   - lastGood: The newest reading from the last successful fetch, or nil if
///     there is none. After a failed fetch, pass the last good reading with
///     `fetchError` true: it ages into STALE on schedule, as `currentStatus`
///     does (FR-005).
///   - fetchError: True when the latest Nightscout fetch failed; every frame
///     then carries "Nightscout unreachable", exactly as `renderLines` adds it.
///   - nowMs: The current time in Unix milliseconds; the first frame's date.
///   - thresholds: The same thresholds the app classifies with.
///   - maxMinutes: The reading's age, in minutes, at which the schedule
///     stops; more than a day counts as a day. The schedule always runs on to
///     the first STALE millisecond, so its last frame is STALE or NO DATA.
/// - Returns: Frames in strictly increasing date order, the first at `nowMs`,
///   each one only where the lines change. No reading gives one NO DATA frame.
public func glanceTimeline(lastGood: GlucoseReading?, fetchError: Bool, nowMs: Int64,
                           thresholds: Thresholds, maxMinutes: Int = 120) -> [GlanceEntry] {
    func frame(at dateMs: Int64) -> GlanceEntry {
        let status = classify(lastGood, nowMs: dateMs, thresholds: thresholds)
        return GlanceEntry(dateMs: dateMs, level: status.level,
                           lines: renderLines(status, fetchError: fetchError))
    }

    var timeline = [frame(at: nowMs)]
    // NO DATA does not change with time; only a fetch can change it.
    guard let reading = lastGood else { return timeline }
    for instant in boundaries(of: reading, after: nowMs, thresholds: thresholds,
                              maxMinutes: maxMinutes) {
        let next = frame(at: instant)
        let shown = timeline[timeline.count - 1]
        if next.level != shown.level || next.lines != shown.lines {
            timeline.append(next)
        }
    }
    return timeline
}

/// When the extension should ask WidgetKit for a new timeline: one reading
/// interval after the first frame, or the date the timeline turns STALE if
/// that comes first, so a fresh reading has its best chance to replace STALE
/// before it shows. A NO DATA timeline, or one that is STALE from its first
/// frame, asks one interval later. The hint follows Nightscout's reading
/// cadence, not the minute ticks of the age text, so it never asks once a
/// minute. Nil only for an empty timeline.
public func reloadAfterMs(for timeline: [GlanceEntry]) -> Int64? {
    guard let first = timeline.first else { return nil }
    let turnsStaleMs = zip(timeline, timeline.dropFirst())
        .first { $0.level != .stale && $1.level == .stale }?.1.dateMs
    return min(clampedSum(first.dateMs, glanceReloadIntervalMs), turnsStaleMs ?? .max)
}

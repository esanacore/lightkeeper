// Render a Status as the short lines every Lightkeeper display shows.
// Mirrors src/lightkeeper/application/monitor.py.

import Foundation

/// Small e-ink panels fit four lines at a readable size (FR-004).
public let maxLines = 4

/// The value text: a number with its arrow, or the sentinel words.
public func valueText(_ reading: GlucoseReading) -> String {
    if reading.isSensorLowSentinel { return "LOW (<40)" }
    if reading.isSensorHighSentinel { return "HIGH (>400)" }
    return "\(reading.mgdl) mg/dL \(reading.trend.arrow)"
}

/// Three to four short ASCII lines. `fetchError` is true when the latest
/// Nightscout fetch failed.
public func renderLines(_ status: Status, fetchError: Bool = false) -> [String] {
    var lines: [String]
    if status.level == .noData || status.reading == nil {
        lines = ["NO DATA", "Check sensor and phone", "Confirm on primary device"]
    } else {
        let reading = status.reading!
        let minutes = status.ageMinutes ?? 0
        var ageText = minutes == 0 ? "just now" : "\(minutes) min ago"
        if status.level == .stale {
            if minutes < 0 { ageText = "time is in the future" }
            lines = ["STALE - DO NOT TRUST", "last: \(valueText(reading))", ageText,
                     "Confirm on primary device"]
        } else {
            lines = [status.level.rawValue, valueText(reading), ageText]
        }
    }
    if fetchError {
        if lines.count < maxLines {
            lines.append("Nightscout unreachable")
        } else {
            // The four-line STALE screen is full; the warning matters more than
            // the "confirm" hint, which STALE's first line already implies.
            lines[maxLines - 1] = "Nightscout unreachable"
        }
    }
    return lines
}

/// Fetch, parse, and classify, degrading safely on failure. On a fetch error
/// the last good reading is re-classified against `nowMs` so it ages into
/// STALE instead of being shown forever.
public func currentStatus(
    entries: Result<[Any], Error>,
    nowMs: Int64,
    thresholds: Thresholds,
    lastGood: Status?
) -> (status: Status, fetchError: Bool) {
    switch entries {
    case .success(let raw):
        let newest = parseEntries(raw).first
        return (classify(newest, nowMs: nowMs, thresholds: thresholds), false)
    case .failure:
        return (classify(lastGood?.reading, nowMs: nowMs, thresholds: thresholds), true)
    }
}

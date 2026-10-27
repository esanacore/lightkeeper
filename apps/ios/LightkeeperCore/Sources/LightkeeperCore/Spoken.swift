// Say a Status in plain sentences, for VoiceOver (FR-017).
// Mirrors src/lightkeeper/application/spoken.py; SpokenVectorTests runs every
// case in spec/spoken_vectors.json, so both say exactly the same words.
//
// Built from the Status, never by parsing the rendered lines, and never more
// current than the screen: the age is always spoken, STALE speaks its warning
// first with no trend word (an arrow is a claim about now), and NO DATA never
// speaks a number. For polite or passive accessibility channels only, never
// an interrupting announcement, and never sound (HAZ-013).

import Foundation

extension Trend {
    /// The arrow in words, the way a screen reader should say it.
    public var spokenName: String {
        switch self {
        case .doubleUp: return "rising quickly"
        case .singleUp: return "rising"
        case .fortyFiveUp: return "rising slowly"
        case .flat: return "steady"
        case .fortyFiveDown: return "falling slowly"
        case .singleDown: return "falling"
        case .doubleDown: return "falling quickly"
        case .unknown: return "trend unknown"
        }
    }
}

/// "mg/dL" as it is spoken.
public let spokenUnit = "milligrams per deciliter"

private let staleWarning = "Stale, do not trust."
private let confirm = "Confirm on the primary device."
private let noData = ["No data.", "Check sensor and phone.", confirm]

/// Whole minutes as "just now", "1 minute ago", or "N minutes ago".
public func spokenAge(_ minutes: Int) -> String {
    switch minutes {
    case 0: return "just now"
    case 1: return "1 minute ago"
    default: return "\(minutes) minutes ago"
    }
}

/// What the screen shows, as a few short sentences in the screen's order.
/// `error` is true when the latest Nightscout fetch failed (`renderLines`'
/// `fetchError`); "Nightscout unreachable." is then added at the end.
public func spokenText(status: Status, error: Bool = false) -> String {
    var sentences = spokenSentences(status)
    if error { sentences.append("Nightscout unreachable.") }
    return sentences.joined(separator: " ")
}

/// The headline for a level that may speak a current number; nil for NO DATA
/// and STALE, which have their own forms.
private func spokenHeadline(_ level: Level) -> String? {
    switch level {
    case .urgentLow: return "Urgent low."
    case .low: return "Low."
    case .inRange: return "In range."
    case .high: return "High."
    case .urgentHigh: return "Urgent high."
    case .noData, .stale: return nil
    }
}

/// The value without any trend: the number and its unit, or the sensor's limit.
private func spokenValue(_ reading: GlucoseReading) -> String {
    if reading.isSensorLowSentinel { return "below 40" }
    if reading.isSensorHighSentinel { return "above 400" }
    return "\(reading.mgdl) \(spokenUnit)"
}

private func spokenSentences(_ status: Status) -> [String] {
    guard status.level != .noData, let reading = status.reading,
          let minutes = status.ageMinutes else {
        return noData
    }

    // classify never pairs a fresh level with a negative age; if a Status
    // ever does, it is spoken as the future-dated STALE form, not as current.
    if status.level == .stale || minutes < 0 {
        if minutes < 0 { return [staleWarning, "Reading time is in the future.", confirm] }
        return [staleWarning, "Last reading \(spokenValue(reading)), \(spokenAge(minutes)).", confirm]
    }

    guard let headline = spokenHeadline(status.level) else { return noData }
    let value = reading.isSensorLowSentinel || reading.isSensorHighSentinel
        ? "Sensor reads \(spokenValue(reading))."
        : "\(spokenValue(reading)), \(reading.trend.spokenName)."
    let age = spokenAge(minutes)
    return [headline, value, age.prefix(1).uppercased() + age.dropFirst() + "."]
}

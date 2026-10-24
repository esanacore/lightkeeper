// Glucose readings and how they are parsed from Nightscout entries.
//
// Pure logic: no network, no clock. A reading that fails validation is
// rejected, never repaired. Showing a wrong number is worse than showing none.
// Mirrors src/lightkeeper/domain/glucose.py line for line.

import Foundation

/// Dexcom and Libre sensors report 40 to 400 mg/dL; Nightscout stores
/// out-of-range values as the sentinels 39 and 401.
public let sensorMinMgdl = 39
public let sensorMaxMgdl = 401

/// Plausible window for an entry's `date` (Unix ms): 2000-01-01 to 2100-01-01.
/// Mirrors MIN_DATE_MS / MAX_DATE_MS in the Python implementation.
public let minDateMs: Double = 946_684_800_000
public let maxDateMs: Double = 4_102_444_800_000

/// Direction of change, using Nightscout's direction strings.
public enum Trend: String, CaseIterable, Sendable {
    case doubleUp = "DoubleUp"
    case singleUp = "SingleUp"
    case fortyFiveUp = "FortyFiveUp"
    case flat = "Flat"
    case fortyFiveDown = "FortyFiveDown"
    case singleDown = "SingleDown"
    case doubleDown = "DoubleDown"
    case unknown = "Unknown"

    /// Plain ASCII arrow, identical across every implementation.
    public var arrow: String {
        switch self {
        case .doubleUp: return "^^"
        case .singleUp: return "^"
        case .fortyFiveUp: return "/"
        case .flat: return "->"
        case .fortyFiveDown: return "\\"
        case .singleDown: return "v"
        case .doubleDown: return "vv"
        case .unknown: return "?"
        }
    }

    /// A nicer glyph for the phone screen. Display only; the rules use `arrow`.
    public var symbol: String {
        switch self {
        case .doubleUp: return "⇈"
        case .singleUp: return "↑"
        case .fortyFiveUp: return "↗"
        case .flat: return "→"
        case .fortyFiveDown: return "↘"
        case .singleDown: return "↓"
        case .doubleDown: return "⇊"
        case .unknown: return "?"
        }
    }
}

/// One sensor glucose value at one moment in time.
public struct GlucoseReading: Equatable, Sendable {
    public let mgdl: Int
    /// Unix time in milliseconds, as Nightscout stores it.
    public let timestampMs: Int64
    public let trend: Trend

    public init(mgdl: Int, timestampMs: Int64, trend: Trend) {
        self.mgdl = mgdl
        self.timestampMs = timestampMs
        self.trend = trend
    }

    public var isSensorLowSentinel: Bool { mgdl <= sensorMinMgdl }
    public var isSensorHighSentinel: Bool { mgdl >= sensorMaxMgdl }
}

public enum ParseError: Error, Equatable {
    case notAnObject
    case notSensorGlucose
    case badValue
    case badDate
}

/// JSON booleans arrive as NSNumber too, so rule them out explicitly, the way
/// the Python code rules out `bool` (a subclass of `int`).
private func number(_ value: Any?) -> Double? {
    if value is Bool { return nil }
    guard let num = value as? NSNumber else { return nil }
    #if canImport(Darwin)
    // On Apple platforms a JSON boolean is a CFBoolean that also casts to any
    // numeric type, so `is Bool` alone is not enough.
    if num === kCFBooleanTrue || num === kCFBooleanFalse { return nil }
    #endif
    return num.doubleValue
}

/// Turn one Nightscout `/api/v1/entries` record into a reading, or throw.
public func parseEntry(_ entry: Any) throws -> GlucoseReading {
    guard let dict = entry as? [String: Any] else { throw ParseError.notAnObject }
    if let type = dict["type"] as? String, type != "sgv" { throw ParseError.notSensorGlucose }
    if dict["type"] != nil, !(dict["type"] is String) { throw ParseError.notSensorGlucose }

    // Range-check the Double before Int(): Int(1e30) is a fatal error in Swift,
    // not a throw, and one such entry would crash the app on every launch.
    guard let sgv = number(dict["sgv"]), sgv.isFinite,
          (Double(sensorMinMgdl)...Double(sensorMaxMgdl)).contains(sgv),
          sgv == sgv.rounded(.towardZero) else {
        throw ParseError.badValue
    }
    let mgdl = Int(sgv)

    // Same for the date: bounded before Int64(), and the bounds also reject
    // seconds-instead-of-milliseconds uploads that would read as 1970.
    guard let dateMs = number(dict["date"]), dateMs.isFinite,
          (minDateMs...maxDateMs).contains(dateMs) else {
        throw ParseError.badDate
    }

    let trend = (dict["direction"] as? String).flatMap(Trend.init(rawValue:)) ?? .unknown
    return GlucoseReading(mgdl: mgdl, timestampMs: Int64(dateMs), trend: trend)
}

/// Parse a list of entries, skipping bad ones, newest first.
public func parseEntries(_ entries: [Any]?) -> [GlucoseReading] {
    // Newest first; when two uploaders share a timestamp the lower value wins,
    // the conservative choice for a glucose display (matches the Python rule).
    (entries ?? []).compactMap { try? parseEntry($0) }.sorted {
        $0.timestampMs != $1.timestampMs ? $0.timestampMs > $1.timestampMs : $0.mgdl < $1.mgdl
    }
}

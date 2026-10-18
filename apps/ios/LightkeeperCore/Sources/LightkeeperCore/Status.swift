// Classify the newest reading into a display status.
//
// The most important rule: old data is never shown as current. Staleness is
// checked before anything else. Mirrors src/lightkeeper/domain/status.py.

import Foundation

/// A reading this far in the future means a clock is wrong somewhere.
public let maxFutureSkewMs: Int64 = 2 * 60 * 1000

public enum Level: String, Sendable {
    case noData = "NO DATA"
    case stale = "STALE"
    case urgentLow = "URGENT LOW"
    case low = "LOW"
    case inRange = "IN RANGE"
    case high = "HIGH"
    case urgentHigh = "URGENT HIGH"

    /// True for anything a person should look at right now.
    public var needsAttention: Bool { self != .inRange }
}

/// Alert thresholds in mg/dL plus the staleness limit. Display settings only.
public struct Thresholds: Equatable, Sendable {
    public let urgentLow: Int
    public let low: Int
    public let high: Int
    public let urgentHigh: Int
    public let staleAfterMs: Int64

    public enum ValidationError: Error { case outOfOrder, staleLimitNotPositive }

    /// Same rule as every implementation: 40 <= urgentLow < low < high < urgentHigh <= 400.
    public init(urgentLow: Int = 55, low: Int = 70, high: Int = 180, urgentHigh: Int = 250,
                staleAfterMs: Int64 = 15 * 60 * 1000) throws {
        guard 40 <= urgentLow, urgentLow < low, low < high, high < urgentHigh, urgentHigh <= 400 else {
            throw ValidationError.outOfOrder
        }
        guard staleAfterMs > 0 else { throw ValidationError.staleLimitNotPositive }
        self.urgentLow = urgentLow
        self.low = low
        self.high = high
        self.urgentHigh = urgentHigh
        self.staleAfterMs = staleAfterMs
    }

    /// The documented defaults (55 / 70 / 180 / 250 mg/dL, stale after 15 minutes).
    public static let defaults: Thresholds = {
        // The literal values satisfy the invariant, so this cannot throw.
        // swiftlint:disable:next force_try
        try! Thresholds()
    }()
}

/// What a display should show, derived from a reading and the time.
public struct Status: Equatable, Sendable {
    public let level: Level
    public let reading: GlucoseReading?
    /// Milliseconds since the reading; clamped to 0 when fresh, raw when stale.
    public let ageMs: Int64?

    /// Whole minutes, floored, matching Python's `seconds // 60`.
    public var ageMinutes: Int? {
        guard let ageMs else { return nil }
        return Int((Double(ageMs) / 1000.0 / 60.0).rounded(.down))
    }
}

/// Decide the display status for the newest reading at `nowMs`.
public func classify(_ reading: GlucoseReading?, nowMs: Int64, thresholds: Thresholds) -> Status {
    guard let reading else { return Status(level: .noData, reading: nil, ageMs: nil) }
    let age = nowMs - reading.timestampMs

    // Checked first, on purpose: stale or future-dated data is never trusted.
    if age > thresholds.staleAfterMs || age < -maxFutureSkewMs {
        return Status(level: .stale, reading: reading, ageMs: age)
    }

    let level: Level
    switch reading.mgdl {
    case ...thresholds.urgentLow: level = .urgentLow
    case ..<thresholds.low: level = .low
    case thresholds.urgentHigh...: level = .urgentHigh
    case (thresholds.high + 1)...: level = .high
    default: level = .inRange
    }
    return Status(level: level, reading: reading, ageMs: max(age, 0))
}

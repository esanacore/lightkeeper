// How a phone screen arranges one status: which shape carries the status
// word, what the hero is, and which vector line goes where. The hierarchy
// lives here rather than in the SwiftUI view, so it is tested on every
// platform the package builds on, against every display vector.
//
// Every word on the glance is a vector line, verbatim: the screen draws
// `renderLines` and nothing else, so the phone and the bedside panel never
// tell two stories. The one exception is the fresh number, which the view
// draws in parts (digits, arrow, unit), and those parts are cut from the
// vector's value line, never rebuilt from the reading.
//
// The shape is keyed by the headline alone, like the panel's treatment
// (src/lightkeeper/infrastructure/panel_layout.py) and the status table in
// assets/brand/tokens.json, so a headline nobody planned for gets the most
// cautious shape: the NO DATA banner, with no hero number: its lines are
// shown verbatim as plain context.
//
// Safety rules this enforces (HAZ-001, HAZ-008):
// - STALE has no hero: no large number, no separate arrow, no unit. Its
//   `last:` line is shown verbatim, struck through, at body size, on the
//   glance and in the panel preview alike (`panelLines`), as the panel
//   strikes it.
// - NO DATA and an unknown headline never show a number as the hero (no
//   large number, arrow or unit); the lines under an unknown headline are
//   plain context.
// - The URGENT, STALE and NO DATA banners are the largest element on the
//   screen. STALE and NO DATA have no hero, so their banner text is set
//   larger than anything else; the URGENT band keeps the fresh number as
//   its hero, so the full-width band is never shorter than that number.
// - The status word is never smaller than .title3.
// - The accessibility label is spokenText(status:error:), from the same
//   Status, so VoiceOver hears exactly what the screen shows.

import Foundation

public struct ScreenPresentation: Equatable, Sendable {
    /// The status colour family, named by its color id in assets/brand/tokens.json.
    public enum Tone: String, CaseIterable, Sendable {
        case inRange = "in-range"
        case low
        case high
        case stale

        /// The token for the chip's border and the band's leading rule.
        public var colorToken: String { rawValue }
        /// The token for the tint behind the word in a chip.
        public var chipToken: String { "chip-\(rawValue)" }
    }

    /// The status word and its colours. When `banner` is not `.none` the
    /// view draws the word in the banner instead of in a chip.
    public struct Chip: Equatable, Sendable {
        /// The vector headline, verbatim.
        public let word: String
        public let tone: Tone
    }

    /// The largest thing on a fresh screen.
    public enum Hero: Equatable, Sendable {
        /// A fresh measured number, cut from the vector's value line
        /// "`digits` `unit` `arrow`": the arrow is the vector's ASCII arrow.
        case number(digits: String, arrow: String, unit: String)
        /// A fresh value line that is not a plain number (the sensor
        /// sentinels "LOW (<40)" and "HIGH (>400)"), verbatim.
        case word(String)
        /// No hero: STALE, NO DATA and any unknown headline.
        case none

        /// The phone glyph for the number's arrow (Trend.symbol), for display
        /// only. Nil when the hero is not a number.
        public var arrowSymbol: String? {
            guard case .number(_, let arrow, _) = self else { return nil }
            return Trend.allCases.first { $0.arrow == arrow }?.symbol ?? arrow
        }
    }

    /// The full-width shape that replaces the chip when a status needs more
    /// than a word on a tint.
    public enum Banner: Equatable, Sendable {
        /// IN RANGE, LOW and HIGH: the word sits in its chip.
        case none
        /// URGENT LOW and URGENT HIGH: an Ink band with a status-colour rule.
        case urgent
        /// STALE: an Ink band with a hatched margin, and the `last:` line struck.
        case stale
        /// NO DATA and any unknown headline: a dashed frame and no hero number.
        case noData
    }

    /// One vector line, drawn verbatim.
    public struct Line: Equatable, Sendable {
        public let text: String
        /// True for STALE's `last:` line: an old value, struck through and
        /// never larger than body text.
        public let struck: Bool
    }

    /// A Dynamic Type text style, smallest first. The view sets each element
    /// in the SwiftUI style of the same name. Apple's type ramp keeps this
    /// order at every content size, from xSmall to AX5, so an element that
    /// is larger here is never smaller on the phone at any text size.
    public enum TextStyle: Int, Comparable, CaseIterable, Sendable {
        case footnote, subheadline, body, title3, title2, title, largeTitle

        public static func < (lhs: TextStyle, rhs: TextStyle) -> Bool {
            lhs.rawValue < rhs.rawValue
        }
    }

    /// The fresh number's size at the default text size, in points. It
    /// scales with Dynamic Type relative to .largeTitle.
    public static let heroPointSize = 96.0
    /// The arrow beside the number: 40 pt beside 96 pt, the same proportion
    /// at every text size, so the arrow is never demoted.
    public static let arrowPointSize = 40.0
    /// A sensor sentinel ("LOW (<40)") is wider than a number, so it starts smaller.
    public static let wordPointSize = 48.0
    /// The age line, in Ink: the number's partner, never small print.
    public static let ageStyle = TextStyle.title3
    /// STALE's struck `last:` line: never above body size, never above the age.
    public static let secondaryStyle = TextStyle.body
    /// The context lines ("Confirm on primary device", "Nightscout unreachable").
    public static let contextStyle = TextStyle.body
    /// The "--" where NO DATA has no number: smaller than its banner.
    public static let placeholderStyle = TextStyle.title2
    /// What NO DATA shows where a number would be. It has no digit in it.
    public static let placeholderText = "--"

    /// Exactly `renderLines(status, fetchError:)`.
    public let lines: [String]
    /// What the panel preview draws: every entry of `lines`, verbatim and in
    /// order, struck exactly where the bedside panel strikes (the `last:`
    /// line under a STALE headline, index 1). Every other line is plain, so
    /// the preview never shows an old value unstruck when the panel strikes it.
    public var panelLines: [Line] {
        lines.enumerated().map { index, text in
            Line(text: text, struck: banner == .stale && index == 1)
        }
    }
    public let chip: Chip
    public let banner: Banner
    public let hero: Hero
    /// `placeholderText` under the NO DATA banner (and an unknown headline's);
    /// nil on every other screen.
    public let placeholder: String?
    /// STALE's `last:` line, struck; nil on every other screen.
    public let secondary: Line?
    /// The age line ("3 min ago"), in Ink; nil where the screen has none (NO DATA).
    public let age: String?
    /// The remaining vector lines, in order ("Confirm on primary device",
    /// "Nightscout unreachable").
    public let context: [String]
    /// What VoiceOver reads for the whole glance: spokenText(status:error:).
    public let accessibilityLabel: String

    /// The hierarchy for a status. `fetchError` is true when the latest
    /// Nightscout fetch failed, as for `renderLines`.
    public init(status: Status, fetchError: Bool = false) {
        self.init(lines: renderLines(status, fetchError: fetchError),
                  accessibilityLabel: spokenText(status: status, error: fetchError))
    }

    /// The hierarchy for lines as rendered. Internal: the public initializer
    /// is the only way in, so the lines and the label always come from one
    /// Status. Tests use this to reach headlines renderLines never makes.
    init(lines: [String], accessibilityLabel: String) {
        let headline = lines.first ?? ""
        let (banner, tone) = Self.shape(for: headline)
        let rest = Array(lines.dropFirst())

        var hero = Hero.none
        var secondary: Line?
        var age: String?
        var context: [String]
        switch banner {
        case .none, .urgent:
            // Fresh: value, then age, then context (panel_layout's roles).
            if let value = rest.first { hero = Self.hero(for: value) }
            age = rest.count > 1 ? rest[1] : nil
            context = Array(rest.dropFirst(2))
        case .stale:
            secondary = rest.first.map { Line(text: $0, struck: true) }
            age = rest.count > 1 ? rest[1] : nil
            context = Array(rest.dropFirst(2))
        case .noData:
            context = rest
        }

        self.lines = lines
        self.chip = Chip(word: headline, tone: tone)
        self.banner = banner
        self.hero = hero
        self.placeholder = banner == .noData ? Self.placeholderText : nil
        self.secondary = secondary
        self.age = age
        self.context = context
        self.accessibilityLabel = accessibilityLabel
    }

    /// The status word's text style: .title3 in a chip, so it is never a
    /// caption; .title on the URGENT, STALE and NO DATA banners. STALE and
    /// NO DATA have no hero, so their banner is the largest text on the
    /// screen; URGENT's band is also held to `bannerMinimumHeight`.
    public var statusStyle: TextStyle {
        switch banner {
        case .none: return .title3
        case .urgent, .stale, .noData: return .title
        }
    }

    /// The banner's minimum height, in points at the default text size; the
    /// view scales it with Dynamic Type exactly as it scales the number.
    /// URGENT keeps the fresh number as its hero, so its full-width band is
    /// made at least the number's size tall: never shorter than the number
    /// beneath it, and wider, so the band is the largest element on the
    /// screen. Nil for the other shapes: a chip sits above the number as a
    /// smaller label, and STALE and NO DATA have no hero to outgrow.
    public var bannerMinimumHeight: Double? {
        banner == .urgent ? Self.heroPointSize : nil
    }

    /// The shape and colour family for a headline. Mirrors the status table
    /// in assets/brand/tokens.json; anything else is treated as NO DATA.
    static func shape(for headline: String) -> (Banner, Tone) {
        switch headline {
        case Level.inRange.rawValue: return (.none, .inRange)
        case Level.low.rawValue: return (.none, .low)
        case Level.high.rawValue: return (.none, .high)
        case Level.urgentLow.rawValue: return (.urgent, .low)
        case Level.urgentHigh.rawValue: return (.urgent, .high)
        case Self.staleHeadline: return (.stale, .stale)
        default: return (.noData, .stale)
        }
    }

    /// A number hero when the value line is exactly "<digits> mg/dL <arrow>"
    /// with a known arrow; otherwise the line itself, verbatim.
    static func hero(for value: String) -> Hero {
        let parts = value.split(separator: " ", omittingEmptySubsequences: false).map(String.init)
        let arrows = Set(Trend.allCases.map(\.arrow))
        guard parts.count == 3, let digits = parts.first, !digits.isEmpty,
              digits.allSatisfy({ $0.isASCII && $0.isNumber }),
              parts[1] == Self.unitText, arrows.contains(parts[2]) else {
            return .word(value)
        }
        return .number(digits: digits, arrow: parts[2], unit: parts[1])
    }

    /// STALE's headline, as `renderLines` writes it.
    static let staleHeadline = "STALE - DO NOT TRUST"

    /// The unit in a vector value line.
    static let unitText = "mg/dL"
}

// MARK: App captions

/// Shown while a refresh someone asked for is running. Static: no spinner,
/// no animation, no ticking.
public let checkingCaption = "checking Nightscout..."

/// "HH:MM", 24-hour, in `timeZone`. For the app's captions only: an absolute
/// time, so nothing has to tick once a second to stay true.
public func clockText(_ date: Date, timeZone: TimeZone = .current) -> String {
    var calendar = Calendar(identifier: .gregorian)
    calendar.timeZone = timeZone
    let parts = calendar.dateComponents([.hour, .minute], from: date)
    return String(format: "%02d:%02d", parts.hour ?? 0, parts.minute ?? 0)
}

/// "checked HH:MM": when the app last asked Nightscout.
public func checkedCaption(_ date: Date, timeZone: TimeZone = .current) -> String {
    "checked \(clockText(date, timeZone: timeZone))"
}

/// "Nightscout unreachable since HH:MM": the first failed fetch of the current outage.
public func offlineCaption(since date: Date, timeZone: TimeZone = .current) -> String {
    "Nightscout unreachable since \(clockText(date, timeZone: timeZone))"
}

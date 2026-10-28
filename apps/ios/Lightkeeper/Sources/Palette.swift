// The brand palette, mirrored from assets/brand/tokens.json (docs/BRAND.md):
// one color per token, named after its id, with its light and dark values.
// tests/test_ios_palette.py holds every value here to that file, so a color
// changes there first. Colors are only ever the second cue: every status
// also has its word and its shape.

import LightkeeperCore
import SwiftUI
import UIKit

enum Palette {
    // Grounds.
    static let night = Color(light: "#0E1116", dark: "#0E1116")
    static let fog = Color(light: "#ECEBE5", dark: "#0E1116")
    static let surface = Color(light: "#F6F5F0", dark: "#161A21")
    static let paper = Color(light: "#E6E5DF", dark: "#DDDCD5")

    // Text and lines. Line is for decorative dividers only; a border that
    // identifies a control, a card or the panel uses Line strong.
    static let ink = Color(light: "#15171C", dark: "#E6E5DF")
    static let muted = Color(light: "#5B6068", dark: "#9AA0A9")
    static let line = Color(light: "#CFCDC4", dark: "#262B33")
    static let lineStrong = Color(light: "#7D7B74", dark: "#646C77")

    // Accent. Beam is for the lamp, rules and text of 24 pt or more; accent
    // text under 24 pt uses Beam text.
    static let beam = Color(light: "#B8730A", dark: "#E0A526")
    static let beamText = Color(light: "#8C5800", dark: "#E0A526")
    static let beamSoft = Color(light: "#F1DDB4", dark: "#3A2E13")

    // Status colors: borders, rules and the stale hatch. As text only at
    // 24 pt regular or 18.66 pt bold and up; smaller, the word is Ink on its chip.
    static let statusInRange = Color(light: "#2E6B4A", dark: "#6CC597")
    static let statusLow = Color(light: "#B3261E", dark: "#FF6B5E")
    static let statusHigh = Color(light: "#B86A00", dark: "#F5A341")
    static let statusStale = Color(light: "#6B6F76", dark: "#9AA0A9")

    // Chip tints, and the words on an Ink band.
    static let chipInRange = Color(light: "#E4E6E0", dark: "#335D4A")
    static let chipLow = Color(light: "#EDE3DE", dark: "#783433")
    static let chipHigh = Color(light: "#EDE6DE", dark: "#734D29")
    static let chipStale = Color(light: "#E7E6E2", dark: "#484C52")
    static let bandText = Color(light: "#E6E5DF", dark: "#0E1116")

    // The panel at night.
    static let nightPaper = Color(light: "#1C1E22", dark: "#1C1E22")
    static let nightInk = Color(light: "#B9B7AE", dark: "#B9B7AE")

    // Pairs drawn from two tokens.
    /// The panel preview's ground: Paper in light mode, Night paper in dark
    /// mode, so the panel is never the brightest thing at the bedside.
    static let panelPaper = Color(light: "#E6E5DF", dark: "#1C1E22")
    /// The panel preview's glyphs: Ink on Paper, Night ink on Night paper.
    static let panelInk = Color(light: "#15171C", dark: "#B9B7AE")
    /// The hard offset shadow under cards and buttons: Beam soft, or Line in dark mode.
    static let hardShadow = Color(light: "#F1DDB4", dark: "#262B33")

    /// The status color for a tone: chip borders and band rules.
    static func status(_ tone: ScreenPresentation.Tone) -> Color {
        switch tone {
        case .inRange: return statusInRange
        case .low: return statusLow
        case .high: return statusHigh
        case .stale: return statusStale
        }
    }

    /// The tint behind the status word in a chip.
    static func chip(_ tone: ScreenPresentation.Tone) -> Color {
        switch tone {
        case .inRange: return chipInRange
        case .low: return chipLow
        case .high: return chipHigh
        case .stale: return chipStale
        }
    }
}

extension Color {
    init(light: String, dark: String) {
        self.init(uiColor: UIColor { trait in
            UIColor(hex: trait.userInterfaceStyle == .dark ? dark : light)
        })
    }
}

extension UIColor {
    /// `hex` is "#RRGGBB", as in tokens.json.
    convenience init(hex: String) {
        let value = UInt64(hex.dropFirst(), radix: 16) ?? 0
        self.init(red: CGFloat((value >> 16) & 0xFF) / 255,
                  green: CGFloat((value >> 8) & 0xFF) / 255,
                  blue: CGFloat(value & 0xFF) / 255, alpha: 1)
    }
}

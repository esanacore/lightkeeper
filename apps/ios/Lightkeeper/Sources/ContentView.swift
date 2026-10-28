// The glance screen, in the Keeper's Logbook order (docs/BRAND.md): the
// status, then the number with its arrow, then the age in Ink, then the
// context lines, then the chrome. Every word on the glance comes from
// ScreenPresentation, which takes it from the vector lines; every status
// has its word and a shape, and color is only the second cue.
//
// What it never does: show a STALE value as the hero (no large number, no
// separate arrow, no unit), show a number on NO DATA, or move. There is no
// animation, no blinking and no per-second ticking; the captions are absolute
// times, and a change is one redraw.

import LightkeeperCore
import SwiftUI

struct ContentView: View {
    @EnvironmentObject var model: GlucoseModel
    @State private var showSettings = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    if model.isConfigured {
                        GlanceView(presentation: model.presentation)
                        captions
                    } else {
                        SetupCard(problem: model.settings.urlProblem) { showSettings = true }
                    }
                    PanelPreview(lines: model.lines)
                    Text(Self.disclaimer)
                        .font(.footnote)
                        .foregroundStyle(Palette.muted)
                }
                .padding(16)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .background(Palette.fog)
            .refreshable { await model.refreshNow() }
            // Inline, so the app's name is never larger than the status.
            .navigationTitle("Lightkeeper")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Settings", systemImage: "gearshape") { showSettings = true }
                }
            }
            .sheet(isPresented: $showSettings) {
                SettingsView().environmentObject(model)
            }
        }
    }

    private static let disclaimer = "Lightkeeper is a secondary display and not a medical device. "
        + "Always confirm on the primary CGM app."

    /// When the app last asked Nightscout, and since when it has failed to
    /// answer: absolute times, so nothing on screen counts seconds.
    private var captions: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(checkedText)
                .foregroundStyle(Palette.muted)
            if let since = model.offlineSince {
                Text(offlineCaption(since: since))
                    .foregroundStyle(Palette.ink)
            }
        }
        .font(.system(.footnote, design: .monospaced))
    }

    /// "checking Nightscout..." while a refresh someone asked for runs, and
    /// before the first answer; "checked HH:MM" after.
    private var checkedText: String {
        guard !model.isChecking, let last = model.lastRefresh else { return checkingCaption }
        return checkedCaption(last)
    }
}

/// Status, hero, age and context: one VoiceOver element that reads the
/// spoken form of the same Status. Every text style comes from the
/// presentation, where the hierarchy is tested against every vector.
struct GlanceView: View {
    let presentation: ScreenPresentation
    /// The fresh number scales with Dynamic Type from today's 96 pt.
    @ScaledMetric(relativeTo: .largeTitle)
    private var heroSize: CGFloat = CGFloat(ScreenPresentation.heroPointSize)
    /// The arrow scales with it, 40 pt beside 96 pt, so it is never demoted.
    @ScaledMetric(relativeTo: .largeTitle)
    private var arrowSize: CGFloat = CGFloat(ScreenPresentation.arrowPointSize)
    /// A sensor sentinel ("LOW (<40)") is wider than a number, so it starts smaller and wraps.
    @ScaledMetric(relativeTo: .largeTitle)
    private var wordSize: CGFloat = CGFloat(ScreenPresentation.wordPointSize)

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            StatusMark(chip: presentation.chip, banner: presentation.banner,
                       style: presentation.statusStyle.textStyle)
            hero
            if let line = presentation.secondary {
                // STALE's last: line: an old value, struck, never above body size.
                Text(line.text)
                    .font(.system(ScreenPresentation.secondaryStyle.textStyle, design: .monospaced))
                    .strikethrough(line.struck, color: Palette.muted)
                    .foregroundStyle(line.struck ? Palette.muted : Palette.ink)
            }
            if let age = presentation.age {
                Text(age)
                    .font(.system(ScreenPresentation.ageStyle.textStyle, design: .monospaced, weight: .semibold))
                    .foregroundStyle(Palette.ink)
            }
            ForEach(Array(presentation.context.enumerated()), id: \.offset) { _, line in
                Text(line)
                    .font(.system(ScreenPresentation.contextStyle.textStyle, design: .monospaced))
                    .foregroundStyle(Palette.ink)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(presentation.accessibilityLabel)
    }

    @ViewBuilder private var hero: some View {
        switch presentation.hero {
        case .number(let digits, _, let unit):
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                // Only the number may shrink to fit; the status and the age never do.
                Text(digits)
                    .font(.system(size: heroSize, weight: .heavy))
                    .monospacedDigit()
                    .lineLimit(1)
                    .minimumScaleFactor(0.5)
                VStack(alignment: .leading, spacing: 0) {
                    Text(presentation.hero.arrowSymbol ?? "")
                        .font(.system(size: arrowSize, weight: .semibold))
                    Text(unit)
                        .font(.subheadline)
                        .foregroundStyle(Palette.muted)
                }
                .fixedSize()
            }
            .foregroundStyle(Palette.ink)
        case .word(let word):
            Text(word)
                .font(.system(size: wordSize, weight: .heavy))
                .foregroundStyle(Palette.ink)
        case .none:
            if let placeholder = presentation.placeholder {
                // Where a number would be on NO DATA: no digit, smaller than the banner.
                Text(placeholder)
                    .font(.system(ScreenPresentation.placeholderStyle.textStyle, design: .monospaced))
                    .foregroundStyle(Palette.ink)
            }
        }
    }
}

extension ScreenPresentation.TextStyle {
    /// The SwiftUI text style of the same name.
    var textStyle: Font.TextStyle {
        switch self {
        case .footnote: return .footnote
        case .subheadline: return .subheadline
        case .body: return .body
        case .title3: return .title3
        case .title2: return .title2
        case .title: return .title
        case .largeTitle: return .largeTitle
        }
    }
}

/// The status word in its shape: a chip, an Ink band with a status rule
/// (URGENT), an Ink band with a hatched margin (STALE), or a dashed frame
/// (NO DATA and anything unknown).
struct StatusMark: View {
    let chip: ScreenPresentation.Chip
    let banner: ScreenPresentation.Banner
    /// From ScreenPresentation.statusStyle: never smaller than .title3.
    let style: Font.TextStyle
    private static let hatchWidth: CGFloat = 8

    var body: some View {
        switch banner {
        case .none:
            Text(chip.word)
                .font(.system(style, weight: .semibold))
                .foregroundStyle(Palette.ink)
                .padding(.horizontal, 12)
                .padding(.vertical, 4)
                .background(Palette.chip(chip.tone), in: RoundedRectangle(cornerRadius: 2))
                .overlay {
                    RoundedRectangle(cornerRadius: 2).strokeBorder(Palette.status(chip.tone), lineWidth: 2)
                }
        case .urgent:
            band
                .overlay(alignment: .leading) {
                    Rectangle().fill(Palette.status(chip.tone)).frame(width: 4)
                }
                .clipShape(RoundedRectangle(cornerRadius: 2))
        case .stale:
            band
                .clipShape(RoundedRectangle(cornerRadius: 2))
                // The hatch sits in the margin beside the band, never under the word.
                .padding(.leading, Self.hatchWidth + 4)
                .background(alignment: .leading) {
                    Hatch(color: Palette.status(chip.tone)).frame(width: Self.hatchWidth)
                }
        case .noData:
            Text(chip.word)
                .font(.system(style, weight: .bold))
                .foregroundStyle(Palette.ink)
                .padding(.horizontal, 12)
                .padding(.vertical, 12)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Palette.surface)
                .overlay {
                    RoundedRectangle(cornerRadius: 2)
                        .strokeBorder(Palette.lineStrong, style: StrokeStyle(lineWidth: 2, dash: [4, 4]))
                }
        }
    }

    /// A full-width Ink band with the word in Band text.
    private var band: some View {
        Text(chip.word)
            .font(.system(style, weight: .bold))
            .foregroundStyle(Palette.bandText)
            .padding(.leading, 16)
            .padding(.trailing, 12)
            .padding(.vertical, 12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Palette.ink)
    }
}

/// hatch-45: one 1 pt diagonal every 4 pt. Texture for STALE's margin only;
/// a solid rule when the person has asked for more contrast.
struct Hatch: View {
    let color: Color
    @Environment(\.colorSchemeContrast) private var contrast

    var body: some View {
        if contrast == .increased {
            Rectangle().fill(color)
        } else {
            HatchLines().stroke(color, lineWidth: 1).clipped()
        }
    }
}

struct HatchLines: Shape {
    var pitch: CGFloat = 4

    func path(in rect: CGRect) -> Path {
        var path = Path()
        var x = rect.minX - rect.height
        while x < rect.maxX {
            path.move(to: CGPoint(x: x, y: rect.maxY))
            path.addLine(to: CGPoint(x: x + rect.height, y: rect.minY))
            x += pitch
        }
        return path
    }
}

/// First launch, or a saved address the app cannot use: an invitation, not
/// an outage. No number and no level word, so it cannot pass for a reading.
struct SetupCard: View {
    let problem: String?
    let openSettings: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Add your Nightscout site to start")
                .font(.system(.title2, weight: .semibold))
                .foregroundStyle(Palette.ink)
            Text(message)
                .foregroundStyle(Palette.ink)
            Button("Open Settings", action: openSettings)
                .buttonStyle(LogbookButtonStyle())
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Palette.surface)
        .overlay {
            RoundedRectangle(cornerRadius: 2).strokeBorder(Palette.lineStrong, lineWidth: 1)
        }
        .background {
            RoundedRectangle(cornerRadius: 2).fill(Palette.hardShadow).offset(x: 3, y: 3)
        }
    }

    private var message: String {
        if let problem { return "The saved address cannot be used. \(problem)" }
        return "Lightkeeper reads glucose from your own Nightscout site and never changes it. "
            + "Add the site's address and a readable token in Settings."
    }
}

/// A logbook button: Ink on Surface with a Line strong edge and a hard
/// shadow; pressed, an Ink fill with Band text. At least 44 pt tall.
struct LogbookButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(.body, weight: .semibold))
            .foregroundStyle(configuration.isPressed ? Palette.bandText : Palette.ink)
            .padding(.horizontal, 16)
            .frame(minHeight: 44)
            .background(configuration.isPressed ? Palette.ink : Palette.surface,
                        in: RoundedRectangle(cornerRadius: 2))
            .overlay {
                RoundedRectangle(cornerRadius: 2).strokeBorder(Palette.lineStrong, lineWidth: 1)
            }
            .background {
                RoundedRectangle(cornerRadius: 2).fill(Palette.hardShadow).offset(x: 3, y: 3)
            }
    }
}

/// The exact lines an e-ink panel would show, so the phone and the bedside
/// screen are never telling two stories. Paper and Ink by day; Night paper
/// and Night ink in dark mode, so the panel is never the brightest thing at
/// the bedside.
struct PanelPreview: View {
    let lines: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            ForEach(Array(lines.enumerated()), id: \.offset) { index, line in
                Text(line)
                    .font(.system(index == 0 ? .headline : .subheadline, design: .monospaced))
                    .foregroundStyle(Palette.panelInk)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Palette.panelPaper, in: NotchedRectangle())
        .overlay { NotchedRectangle().strokeBorder(Palette.lineStrong, lineWidth: 2) }
        .accessibilityHidden(true)
    }
}

/// The bezel: a rectangle with each corner notched by one 2 pt step.
struct NotchedRectangle: InsettableShape {
    var step: CGFloat = 2
    var inset: CGFloat = 0

    func path(in rect: CGRect) -> Path {
        let r = rect.insetBy(dx: inset, dy: inset)
        let s = min(step, r.width / 2, r.height / 2)
        var path = Path()
        path.move(to: CGPoint(x: r.minX + s, y: r.minY))
        path.addLine(to: CGPoint(x: r.maxX - s, y: r.minY))
        path.addLine(to: CGPoint(x: r.maxX - s, y: r.minY + s))
        path.addLine(to: CGPoint(x: r.maxX, y: r.minY + s))
        path.addLine(to: CGPoint(x: r.maxX, y: r.maxY - s))
        path.addLine(to: CGPoint(x: r.maxX - s, y: r.maxY - s))
        path.addLine(to: CGPoint(x: r.maxX - s, y: r.maxY))
        path.addLine(to: CGPoint(x: r.minX + s, y: r.maxY))
        path.addLine(to: CGPoint(x: r.minX + s, y: r.maxY - s))
        path.addLine(to: CGPoint(x: r.minX, y: r.maxY - s))
        path.addLine(to: CGPoint(x: r.minX, y: r.minY + s))
        path.addLine(to: CGPoint(x: r.minX + s, y: r.minY + s))
        path.closeSubpath()
        return path
    }

    func inset(by amount: CGFloat) -> NotchedRectangle {
        var shape = self
        shape.inset += amount
        return shape
    }
}

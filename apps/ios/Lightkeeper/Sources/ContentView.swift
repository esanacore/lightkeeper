// The glance screen: a big calm number, the status word, how old it is.
// Colors come from the brand palette (docs/BRAND.md); status always travels
// with its word, never color alone.

import LightkeeperCore
import SwiftUI

struct ContentView: View {
    @EnvironmentObject var model: GlucoseModel
    @State private var showSettings = false

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 20) {
                statusBadge
                numberBlock
                Text(ageLine)
                    .font(.system(.callout, design: .monospaced))
                    .foregroundStyle(Palette.muted)
                if model.fetchError {
                    Text("Nightscout unreachable")
                        .font(.system(.callout, design: .monospaced))
                        .foregroundStyle(Palette.statusStale)
                }
                Spacer()
                panelPreview
                Text("Lightkeeper is a secondary display and not a medical device. Always confirm on the primary CGM app.")
                    .font(.footnote)
                    .foregroundStyle(Palette.muted)
            }
            .padding(24)
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            .background(Palette.fog)
            .navigationTitle("Lightkeeper")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Settings", systemImage: "gearshape") { showSettings = true }
                }
            }
            .sheet(isPresented: $showSettings) {
                SettingsView().environmentObject(model)
            }
            .refreshable { await model.refresh() }
        }
    }

    private var statusBadge: some View {
        Text(model.status.level == .stale ? "STALE - DO NOT TRUST" : model.status.level.rawValue)
            .font(.system(.caption, design: .monospaced).weight(.semibold))
            .padding(.horizontal, 10).padding(.vertical, 5)
            .overlay(RoundedRectangle(cornerRadius: 6).stroke(statusColor, lineWidth: 1))
            .foregroundStyle(statusColor)
            .accessibilityLabel("Status: \(model.lines.first ?? "")")
    }

    private var numberBlock: some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            Text(bigNumber)
                .font(.system(size: 96, weight: .heavy, design: .default))
                .monospacedDigit()
                .foregroundStyle(model.status.level == .stale ? Palette.statusStale : Palette.ink)
                .minimumScaleFactor(0.5)
                .lineLimit(1)
            if let r = model.status.reading, !r.isSensorLowSentinel, !r.isSensorHighSentinel {
                VStack(alignment: .leading) {
                    Text(r.trend.symbol).font(.system(size: 40, weight: .semibold))
                    Text("mg/dL").font(.caption).foregroundStyle(Palette.muted)
                }
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(model.lines.dropFirst().first ?? "")
    }

    private var bigNumber: String {
        guard let r = model.status.reading, model.status.level != .noData else { return "--" }
        if r.isSensorLowSentinel { return "LOW" }
        if r.isSensorHighSentinel { return "HIGH" }
        return String(r.mgdl)
    }

    private var ageLine: String {
        model.lines.count > 2 ? model.lines[2] : (model.lines.last ?? "")
    }

    private var statusColor: Color {
        switch model.status.level {
        case .inRange: return Palette.statusInRange
        case .low, .urgentLow: return Palette.statusLow
        case .high, .urgentHigh: return Palette.statusHigh
        case .stale, .noData: return Palette.statusStale
        }
    }

    /// The exact four lines an e-ink panel would show, so the phone and the
    /// bedside screen are never telling two stories.
    private var panelPreview: some View {
        VStack(alignment: .leading, spacing: 2) {
            ForEach(Array(model.lines.enumerated()), id: \.offset) { index, line in
                Text(line)
                    .font(.system(index == 0 ? .headline : .subheadline, design: .monospaced))
                    .foregroundStyle(Palette.inkOnPaper)
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Palette.paper)
        .clipShape(RoundedRectangle(cornerRadius: 6))
        .overlay(RoundedRectangle(cornerRadius: 6).stroke(Palette.line, lineWidth: 1))
        .accessibilityHidden(true)
    }
}

struct SettingsView: View {
    @EnvironmentObject var model: GlucoseModel
    @Environment(\.dismiss) private var dismiss
    @State private var token = Keychain.readToken() ?? ""

    var body: some View {
        NavigationStack {
            Form {
                Section("Nightscout") {
                    TextField("https://your-site.example", text: $model.settings.nightscoutURL)
                        .keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled()
                    SecureField("Readable token (never the API secret)", text: $token)
                }
                Section("Display thresholds (mg/dL)") {
                    Stepper("Urgent low: \(model.settings.urgentLow)", value: $model.settings.urgentLow, in: 40...100)
                    Stepper("Low: \(model.settings.low)", value: $model.settings.low, in: 41...150)
                    Stepper("High: \(model.settings.high)", value: $model.settings.high, in: 100...350)
                    Stepper("Urgent high: \(model.settings.urgentHigh)", value: $model.settings.urgentHigh, in: 101...400)
                    Stepper("Stale after: \(model.settings.staleMinutes) min", value: $model.settings.staleMinutes, in: 6...60)
                    Text("These change what the display says, not what the pump does. Agree them with your care team.")
                        .font(.footnote).foregroundStyle(Palette.muted)
                }
            }
            .navigationTitle("Settings")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        Keychain.writeToken(token)
                        model.settings.save()
                        dismiss()
                        Task { await model.refresh() }
                    }
                }
            }
        }
    }
}

/// Brand palette (docs/BRAND.md). Light and dark pairs.
enum Palette {
    static let fog = Color(light: "#ECEBE5", dark: "#0E1116")
    static let paper = Color(light: "#E6E5DF", dark: "#DDDCD5")
    static let ink = Color(light: "#15171C", dark: "#E6E5DE")
    static let inkOnPaper = Color(light: "#121212", dark: "#141414")
    static let muted = Color(light: "#5B6068", dark: "#9AA0A9")
    static let line = Color(light: "#CFCDC4", dark: "#262B33")
    static let beam = Color(light: "#B8730A", dark: "#E0A526")
    static let statusInRange = Color(light: "#2E6B4A", dark: "#6CC597")
    static let statusLow = Color(light: "#B3261E", dark: "#FF6B5E")
    static let statusHigh = Color(light: "#B86A00", dark: "#F5A341")
    static let statusStale = Color(light: "#6B6F76", dark: "#9AA0A9")
}

extension Color {
    init(light: String, dark: String) {
        self.init(uiColor: UIColor { trait in
            UIColor(hex: trait.userInterfaceStyle == .dark ? dark : light)
        })
    }
}

extension UIColor {
    convenience init(hex: String) {
        var value: UInt64 = 0
        Scanner(string: String(hex.dropFirst())).scanHexInt64(&value)
        self.init(red: CGFloat((value >> 16) & 0xFF) / 255,
                  green: CGFloat((value >> 8) & 0xFF) / 255,
                  blue: CGFloat(value & 0xFF) / 255, alpha: 1)
    }
}

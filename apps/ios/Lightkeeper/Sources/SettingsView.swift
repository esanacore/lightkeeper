// The settings sheet: the Nightscout address and readable token, and the
// display thresholds. The address is checked as it is typed, with the reason
// shown, by the same NightscoutClient initializer every fetch goes through,
// so an address the app cannot use can never be saved.

import LightkeeperCore
import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var model: GlucoseModel
    @Environment(\.dismiss) private var dismiss
    @State private var token = Keychain.readToken() ?? ""
    // Edits land in a draft, so swiping the sheet away never applies
    // half-finished thresholds to the live display (HAZ-006).
    @State private var draft = Settings()
    @State private var check = CheckState.idle

    private enum CheckState: Equatable {
        case idle
        case checking
        case done(String)
    }

    var body: some View {
        NavigationStack {
            Form {
                nightscoutSection
                thresholdsSection
            }
            .navigationTitle("Settings")
            .onAppear { draft = model.settings }
            .onChange(of: draft.nightscoutURL) { _, url in
                // A pasted address often carries a space or a newline at an end.
                let trimmed = url.trimmingCharacters(in: .whitespacesAndNewlines)
                if trimmed != url { draft.nightscoutURL = trimmed }
                check = .idle
            }
            .onChange(of: token) { _, _ in check = .idle }
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        guard draft.save() else { return }
                        Keychain.writeToken(token)
                        model.settings = draft
                        dismiss()
                        Task { await model.refreshNow() }
                    }
                    .disabled(!draft.canSave)
                }
            }
        }
    }

    private var nightscoutSection: some View {
        Section {
            TextField("https://your-site.example", text: $draft.nightscoutURL)
                .keyboardType(.URL)
                .textContentType(.URL)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .accessibilityLabel("Nightscout address")
            if let reason = draft.urlProblem {
                problem(reason, spoken: "Address not usable: \(reason)")
            }
            SecureField("Readable token (never the API secret)", text: $token)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
            Button("Check connection", action: runCheck)
                .disabled(!draft.isConfigured || check == .checking)
                .accessibilityValue(checkWords ?? "")
            if let words = checkWords {
                Text(words)
                    .font(.footnote)
                    .foregroundStyle(Palette.ink)
                    .accessibilityHidden(true)
            }
        } header: {
            Text("Nightscout")
        } footer: {
            Text(Self.tokenFootnote)
        }
    }

    private static let tokenFootnote = "Make a readable token in Nightscout: Admin Tools, Subjects, "
        + "add a subject with the readable role, and copy its access token here. Never paste the "
        + "API secret: it can change your Nightscout, and Lightkeeper only ever reads. The token "
        + "stays in this phone's Keychain and travels only in a request header, never in an address."

    private static let thresholdsFootnote = "Thresholds change only which word the display shows. "
        + "They do not affect dosing or the primary app's alarms. Match them to the alert settings "
        + "already in the primary app."

    private var thresholdsSection: some View {
        Section {
            Stepper("Urgent low: \(draft.urgentLow)", value: $draft.urgentLow,
                    in: Settings.urgentLowRange, step: Settings.thresholdStep)
            Stepper("Low: \(draft.low)", value: $draft.low,
                    in: Settings.lowRange, step: Settings.thresholdStep)
            Stepper("High: \(draft.high)", value: $draft.high,
                    in: Settings.highRange, step: Settings.thresholdStep)
            Stepper("Urgent high: \(draft.urgentHigh)", value: $draft.urgentHigh,
                    in: Settings.urgentHighRange, step: Settings.thresholdStep)
            Stepper("Stale after: \(draft.staleMinutes) min", value: $draft.staleMinutes,
                    in: Settings.staleRange)
            if let caution = draft.staleCaution {
                problem(caution, spoken: "Caution: \(caution)")
            }
            if let message = draft.validationMessage {
                problem(message, spoken: "Invalid thresholds: \(message)")
            }
            Button("Reset to defaults") { draft = draft.resettingThresholds() }
        } header: {
            Text("Display thresholds (mg/dL)")
        } footer: {
            Text(Self.thresholdsFootnote)
        }
    }

    /// A warning row: Ink words beside a triangle, never colour alone.
    private func problem(_ text: String, spoken: String) -> some View {
        Label(text, systemImage: "exclamationmark.triangle")
            .font(.footnote)
            .foregroundStyle(Palette.ink)
            .accessibilityLabel(spoken)
    }

    private var checkWords: String? {
        switch check {
        case .idle: return nil
        case .checking: return checkingCaption
        case .done(let words): return words
        }
    }

    /// One read-only GET with what is typed now, saved or not: the same
    /// request, header and redirect guard as every fetch.
    private func runCheck() {
        let url = draft.nightscoutURL
        let typed = token
        guard let client = try? NightscoutClient(baseURL: url, token: typed.isEmpty ? nil : typed) else {
            return
        }
        let thresholds = draft.thresholds
        check = .checking
        Task {
            let result = await client.checkConnection()
            // An edit since the tap makes this answer about something else.
            guard draft.nightscoutURL == url, token == typed else { return }
            let nowMs = Int64(Date().timeIntervalSince1970 * 1000)
            check = .done(connectionReport(result, nowMs: nowMs, thresholds: thresholds))
        }
    }
}

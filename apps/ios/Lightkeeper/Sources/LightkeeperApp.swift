// Lightkeeper companion app: the read-only layer (ADR-0008, Phase 5a).
//
// Shows the same status every Lightkeeper display shows, with the same rules
// from LightkeeperCore. No pump or sensor communication exists in this app.
// The bolus request screen (Phase 5b) is not built yet and is gated by the
// promotion criteria in ADR-0008.

import SwiftUI

@main
struct LightkeeperApp: App {
    @StateObject private var model = GlucoseModel()
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(model)
                .task { await model.start() }
        }
        .onChange(of: scenePhase) { _, phase in
            // Coming back from the background: age the last reading against
            // the clock immediately, then fetch. The screen must never show a
            // pre-background "3 min ago" while the network round trip runs.
            if phase == .active {
                model.reclassify()
                Task { await model.refresh() }
            }
        }
    }
}

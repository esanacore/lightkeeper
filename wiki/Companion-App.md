# Companion App

The companion app is the iOS app from ADR-0008, written up here for people rather than for the ADR template. It has two deliberately separate layers: a read-only layer that exists today in `apps/ios/`, and a bolus request layer that does not exist yet and is gated behind promotion criteria. Sources: `docs/adr/0008-companion-app-and-bolus-requests-via-trio.md` and `apps/ios/README.md` in the repository; the ADR is summarized in [[Architecture Decisions]].

Lightkeeper is a secondary display and not a medical device. Always confirm on the primary CGM app before acting.

## Why it exists

The person with diabetes wants an app of their own that shows glucose and trend clearly and lets them enter a manual bolus, without this project writing insulin delivery software. Two facts shape the answer. An Omnipod 5 pod pairs with one controller; while Trio owns the pod, no other app can command it, so sending a bolus directly would make Lightkeeper the pump controller, which ADR-0004 rules out. And Trio has a Remote Control feature: another app sends a command over Apple Push Notifications, signed with a shared secret, and Trio runs its own checks and accepts or rejects. The documented client today is LoopFollow.

## The read-only layer (Phase 5a), what exists now

`apps/ios/LightkeeperCore/` is a Swift package with the display rules (parse, classify, render) and a read-only Nightscout client. Its `VectorTests` target runs every case in `spec/display_vectors.json` and asserts the spec version, so the Swift rules are held identical to the Python and C++ ones. The client accepts HTTPS only, caps the response size, and refuses redirects that change scheme or host. Numbers too large for `Int` throw instead of crashing, and one poisoned entry does not blank the list (HAZ-012, HAZ-011).

`apps/ios/Lightkeeper/` is the SwiftUI app: a glance screen showing the same status every other Lightkeeper display shows, big and calm, plus settings. On returning to the foreground it re-ages the last reading immediately, and a STALE number is shrunk and struck through so a glance cannot read it as current. Settings edits land in a draft; Save is disabled, with the reason shown, while the threshold set is invalid, and an invalid set found on disk resets to defaults so screen and rules always agree. Thresholds change only which word the display shows. They do not affect dosing or the primary app's alarms. Match them to the alert settings already in the primary app.

The readable token lives in the Keychain, protected until first unlock, and is never written to UserDefaults or logs. There is no Mac in the project: `.github/workflows/ios.yml` runs the tests and builds the app on GitHub's macOS runners, and TestFlight distribution will use the same path with signing secrets added.

Still to come in this layer: widgets and a watch complication, background refresh, mmol/L, delta and IOB from Nightscout's device status, and recent treatments. All of that reads and shows data, so ADR-0004 covers it. It is requirement FR-012, verified.

## The bolus request path (Phase 5b), what is planned

A bolus screen that composes a request and sends it to Trio over Trio's remote protocol. The app never talks to the pod or the sensor. Trio alone decides whether insulin moves. The app shows a request as "pending" until Trio answers, shows rejections with Trio's reason, and never displays anything as delivered on its own authority. If the app's own glucose display is STALE at that moment, the screen is disabled.

ADR-0008 restates ADR-0004's rule for this: dosing requests may only be expressed through an established community controller's own remote protocol, which applies that controller's safety limits.

## What Trio enforces

Trio's guardrails apply on the phone regardless of what the sender asked for, per triodocs.org and LoopFollow's documentation: remote control is off by default and must be switched on in Trio; commands are signed with a shared secret; Trio enforces its own Max Bolus and Max IOB; it rejects a bolus if one over 20% of the requested size was delivered in the last 10 minutes; and it drops commands older than 10 minutes or timestamped in the future.

LoopFollow's docs add the corollary that shapes HAZ-010: display lag can make a dose look failed, so a client must assume a previous remote bolus was delivered rather than resend.

## Promotion criteria

ADR-0008 stays Proposed until all of these are true:

1. A hazard analysis for the bolus screen is in `docs/SAFETY.md` (wrong amount, double send, pending state, rejection handling, stale display at the moment of request), each hazard with a tested mitigation. HAZ-010 is the first entry; see [[Safety]].
2. The remote protocol is understood from a primary source (LoopFollow's implementation and TrioDocs), and a fake Trio endpoint exists so every rejection path can be exercised without insulin.
3. The read-only layer has shipped to TestFlight and been used for at least two weeks.
4. The person with diabetes agrees to the design, and their care team knows the app can request boluses.

Gate: the person with diabetes decides; Eric runs the hazard review.

## Status

Read-only layer: builds and tests in CI; nothing on TestFlight yet. Bolus request layer: no code. The safe fallback, if the hazard review does not close, is no bolus screen at all; the read-only layer ships regardless.

See [[Roadmap]] for where Phase 5 sits, and [[Testing and Quality]] for how the Swift port is held to the shared vectors.

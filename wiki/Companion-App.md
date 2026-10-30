# Companion App

There are two companion apps, written up here for people rather than for the ADR template. The iOS app from ADR-0008 has two deliberately separate layers: a read-only layer that exists today in `apps/ios/`, and a bolus request layer that does not exist yet and is gated behind promotion criteria. The Android app in `apps/android/` is read-only (FR-020) and has no bolus layer. Sources: `docs/adr/0008-companion-app-and-bolus-requests-via-trio.md`, `apps/ios/README.md` and `apps/android/README.md` in the repository; the ADR is summarized in [[Architecture Decisions]].

Lightkeeper is a secondary display and not a medical device. Always confirm on the primary CGM app before acting.

## Why it exists

The person with diabetes wants an app of their own that shows glucose and trend clearly and lets them enter a manual bolus, without this project writing insulin delivery software. Two facts shape the answer. An Omnipod 5 pod pairs with one controller; while Trio owns the pod, no other app can command it, so sending a bolus directly would make Lightkeeper the pump controller, which ADR-0004 rules out. And Trio has a Remote Control feature: another app sends a command over Apple Push Notifications, signed with a shared secret, and Trio runs its own checks and accepts or rejects. The documented client today is LoopFollow.

## The read-only layer (Phase 5a), what exists now

`apps/ios/LightkeeperCore/` is a Swift package with the display rules (parse, classify, render) and a read-only Nightscout client. Its `VectorTests` target runs every case in `spec/display_vectors.json` and asserts the spec version, so the Swift rules are held identical to the Python and C++ ones. The client accepts HTTPS only, caps the response size, and refuses redirects that change scheme or host. Numbers too large for `Int` throw instead of crashing, and one poisoned entry does not blank the list (HAZ-012, HAZ-011). The package also holds the spoken form (`SpokenVectorTests` runs every sentence in `spec/spoken_vectors.json`, so the VoiceOver label is the same sentence the Python spoken form gives), the phone's glance hierarchy (`Presentation.swift`, held to every vector by `PresentationTests`), and the glance timeline (`GlanceTimeline.swift`). The client accepts only a site address: https, a host and an optional port, with no path, query, fragment or login.

`apps/ios/Lightkeeper/` is the SwiftUI app: a glance screen showing the same status every other Lightkeeper display shows, big and calm, plus settings. On returning to the foreground it re-ages the last reading immediately, and on STALE it shows no large number, arrow or unit: the STALE banner is the largest text on screen and the old value appears only in the struck `last:` line at body size. Settings edits land in a draft; Save is disabled, with the reason shown, while the threshold set is invalid, and an invalid set found on disk resets to defaults so screen and rules always agree. Thresholds change only which word the display shows. They do not affect dosing or the primary app's alarms. Match them to the alert settings already in the primary app.

First launch shows "Add your Nightscout site to start" and makes no fetch until a usable address is saved. In Settings, enter just the site (`https://your-site.example`, nothing after the name) and a readable token made in Nightscout's Admin Tools, Subjects. Check connection makes one read-only request and says: connected, with the newest reading's age; Nightscout refused the token; this Nightscout needs a token to be read (the token field is empty); the site could not be reached; or the answer was not a Nightscout one. Thresholds step by 5 with Reset to defaults, and a caution shows when Stale after is above 15 minutes. The glance's VoiceOver label is the spoken form, for example "In range. 112 milligrams per deciliter, steady. 3 minutes ago."; hearing VoiceOver read it on a device is still to do (GAP-009). Captions are absolute times: `checked HH:MM`, and `Nightscout unreachable since HH:MM` during an outage.

The readable token lives in the Keychain, protected until first unlock, and is never written to UserDefaults or logs. There is no Mac in the project: `.github/workflows/ios.yml` runs the package tests (on macOS and Linux), builds the app, and runs its unit tests on an iOS simulator (`apps/ios/Lightkeeper/Tests/`: an invalid stored threshold set resets to the defaults, and returning to the foreground turns an old reading STALE without a fetch). The reworked views and the new app tests passed there for the first time on the push to `main` at commit `1c0cdb8`; the app has not yet run on a device (GAP-009). TestFlight distribution will use the same path with signing secrets added.

Still to come in this layer: widgets and a watch complication, background refresh, mmol/L, delta and IOB from Nightscout's device status, and recent treatments. All of that reads and shows data, so ADR-0004 covers it. It is requirement FR-012, verified. The glance timeline those widgets will draw from is in place (`GlanceTimeline.swift`): every frame is scheduled ahead with STALE among them, tested against the shared vectors (FR-019); the widget extension waits on Apple signing and App Groups.

## The Android app (read-only), what exists now

`apps/android/` is a read-only app for Android phones, written in Kotlin with framework Views. No AndroidX, Compose or third-party library is in the APK, only the Kotlin standard library and its annotations. It reads Nightscout and nothing else: no pump or sensor code, no alarm, no widget.

There is no fourth copy of the rules. The app compiles the firmware's `glucose_rules`, `nightscout_json` and `panel_bitmap` in place, by path, and reaches them through one small JNI file, so every line on the glance and every pixel of its panel image come from the firmware's own C++. A reading coming back from Kotlin is checked again by the firmware's parser, so a bad one can only show NO DATA. The instrumented tests run every case in `spec/display_vectors.json`, `spec/response_vectors.json` and `spec/panel_vectors.json` through that code on a phone or emulator, and assert the vectors' `spec_version` as the other three suites do.

The glance follows the Keeper's Logbook order, and every word on it comes from the vector lines. The status chip comes first, at 20 sp bold. A fresh number is the hero, with its arrow beside it and the unit under it. On STALE there is no big number, separate arrow or unit: the STALE banner is the largest text, and the old value appears only in the struck `last:` line at body size. NO DATA, and any headline nobody planned for, gets a dashed frame and `--` where a number would be. Under the glance sit `checked HH:MM` (`checking Nightscout...` before the first answer) and, during an outage, `Nightscout unreachable since HH:MM`, then the real 1-bit panel image at the 296x128 size, stamped with the local time it was drawn. TalkBack reads the status area as the display lines in order; the spoken sentences of `spec/spoken_vectors.json`, which the iOS app uses, are not on Android yet.

The app fetches when its screen opens and every 60 seconds while it is visible. It re-ages the last good reading every 30 seconds and the moment the screen comes back, with no fetch, so it turns STALE on time even when fetches stop. Coming back also fetches, but only when the last fetch began 15 seconds ago or more. One fetch runs at a time, and one with no answer after 20 seconds is cancelled and shown as `Nightscout unreachable`. Nothing runs while the screen is hidden. Until a usable address is saved, the glance is replaced by "Add your Nightscout site to start", with no number and no level word, and the app makes no fetch.

Settings check the address as it is typed, with the iOS app's rule and its reasons word for word: https, and just the site. The thresholds step by 5 over the iOS ranges and Stale after by 1 from 6 to 60, with the iOS caution above 15 minutes. Save is refused for an invalid set, and an invalid set found on disk is reset to the defaults and written back. The readable token is sealed with AES-256-GCM under an Android Keystore key and travels only in the `api-secret` header. The app asks for one permission, `INTERNET`; backup and cleartext traffic are off, and there are no notifications, alarms or widgets. It ships as a sideloaded debug APK, about 1 MB, for Android 8.0 or later, built and installed as `apps/android/README.md` says (on Windows, from a short checkout path).

Thresholds change only which word the display shows. They do not affect dosing or the primary app's alarms. Match them to the alert settings already in the primary app.

82 JVM unit tests and lint pass, and the 39 instrumented tests passed on an API 36.1 emulator through `adb shell am instrument`. `.github/workflows/android.yml` first ran on the push to `main` at commit `1c0cdb8`: the build, the unit tests and lint passed, and 38 of the 39 instrumented tests. The 39th, `testThePanelIsDrawnAtAWholeNumberScale`, failed because the default emulator screen, 320 px wide, is narrower than the 296 px panel with its frame and the glance's margins, so the panel rightly drew nothing. The workflow now gives the emulator a Pixel 6 screen, and on it all 39 pass (on `main` at commit `5113fb5`). Nothing has run on a phone (GAP-013), and Kotlin coverage is not measured (GAP-014). Not yet: Check connection, TalkBack sentences, a widget (it needs the exact-alarm decision first), and release signing. The shape of this first slice (framework Views, the C++ through JNI, a sideloaded APK, Android 8.0 or later, no widget), the stamp on the panel image, the 15-second rule for fetching on return, the application id `com.esanacore.lightkeeper` and the three ABIs (arm64-v8a, armeabi-v7a, x86_64) are defaults pending Eric's decision.

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

Read-only layer: builds and tests in CI, where the reworked SwiftUI views and their app tests first passed on the simulator on the push to `main`; it has not run on a device, and nothing is on TestFlight yet. Bolus request layer: no code. The safe fallback, if the hazard review does not close, is no bolus screen at all; the read-only layer ships regardless. Android app: read-only, a sideloaded debug APK whose tests pass on an emulator; in CI its build, unit tests and lint pass, and so do all 39 emulator tests on a Pixel 6 screen; it has not been on a phone.

See [[Roadmap]] for where Phase 5 sits, and [[Testing and Quality]] for how the Swift port and the Android app are held to the shared vectors.

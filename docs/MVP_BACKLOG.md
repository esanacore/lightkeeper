# MVP Backlog

The phased rollout of the whole stack. Phases gate on evidence, not dates. `TODO.md` holds individual work items.

## Phase 0: Foundation (this repository)

- [x] Bootstrap the repo with the engineering constitution.
- [x] Write the safety boundary, hazard log, and ADRs 0001 to 0005.
- [x] `lightkeeper` 0.1.0: parse, classify, render, degrade safely, with tests (FR-001 to FR-006).
- [ ] Kaitlin reviews `docs/SAFETY.md` (including HAZ-014 to HAZ-016 and the desktop window and the Android app) and the default thresholds, and signs the ADR-0011 section of `docs/SAFETY_REVIEW.md`.

## Phase 1: Data Hub

- [ ] Choose hosting and deploy Nightscout over HTTPS, with authentication defaulted to deny (ADR-0003).
- [ ] Create a readable-role token for displays.
- [ ] Configure backups and test a restore.
- [ ] Run `lightkeeper` against it and close GAP-003.

## Phase 2: Trio in Open Loop

- [ ] Kaitlin talks with her endocrinologist about moving to Trio and reviews her current settings.
- [ ] Get an Apple Developer account and build Trio from source.
- [ ] Connect the Dexcom G7 app as the CGM source, turn off iOS automatic updates, and confirm Nightscout uploads.
- [ ] Pair Omnipod 5 pods with Trio (supported on main since Trio v1.0.0) in open loop, so Trio only suggests. Keep a backup DASH pod for the first switch, and don't fill the pod until Trio shows the pairing screen.
- [ ] Log every pod change, fault, and suggestion mismatch for at least two weeks.

## Phase 3: Closed Loop

- [ ] Settings validated with her care team; promotion criteria in ADR-0002 met.
- [ ] Enable closed loop conservatively, review data weekly at first.
- [ ] Keep the official Omnipod 5 app or Controller as a documented fallback.

## Phase 4: Our Hardware Layer

See `docs/ROADMAP.md` for how phases relate and what gates each one.

- [ ] Buy Tier 1 hardware from `docs/HARDWARE.md`.
- [~] Raspberry Pi e-paper bedside display (FR-007), side by side with the primary app for one full sensor session. Done: the integer-only 1-bit panel layout at six panel sizes (pinned by `spec/panel_vectors.json`), stamped PNG and BMP exports, and the hardened systemd service with a watchdog. Next: the SPI panel driver once the parts arrive.
- [~] Desktop glance window (FR-018, 2026-10-28): the real panel pixels on a monitor, aging into STALE on its own clock; checked by hand on Windows 11. Next: macOS and Linux with a display (GAP-015).
- [~] Home Assistant sensor and alerts (FR-008). Built over MQTT discovery (ADR-0010, HAZ-013) and tested against a fake broker; next, a check against a real Home Assistant (GAP-002).
- [x] ESP32 safety rules in C++ with shared-vector parity tests (ADR-0006).
- [x] ESP32 panel rasterizer in C++ at pixel parity with Python (`lib/panel_bitmap`, FR-016, 2026-10-28).
- [~] Xteink X4/X3 device build and side-by-side validation (FR-010). Done: a build-only PlatformIO skeleton for the bench ESP32-S3 and the X4 that prints the NO DATA panel over USB serial. Next: Wi-Fi, HTTPS and the panel driver (D11), then validation.

## Phase 5: Companion App (ADR-0008)

- [~] Read-only iOS app: glance screen, settings, Keychain token, CI build, and (2026-10-28) the STALE-first glance hierarchy, first-run setup, Check connection, the VoiceOver spoken form and the glance timeline core (done); the widget extension (needs D10), IOB, recent treatments, watch complication (next).
- [~] Read-only Android app (FR-020, 2026-10-28): the glance, settings, the sealed token and the panel image, every line and pixel from the firmware's C++ through JNI, tested on an emulator, as a sideloaded debug APK. Its build, unit tests and lint pass in CI, and so do all 39 emulator tests on a Pixel 6 screen. Next: a real phone (GAP-013), Check connection, TalkBack sentences, release signing, and a widget after the exact-alarm decision (D9).
- [ ] Study LoopFollow's Trio Remote Control implementation; build a fake Trio endpoint for tests.
- [ ] Hazard analysis for the bolus request screen in `docs/SAFETY.md`.
- [ ] Bolus request screen, gated behind the promotion criteria in ADR-0008.

## Phase 6: Community

- [x] Publish the demo page (2026-10-24, https://esanacore.github.io/lightkeeper/).
- [x] Demo page v2: the real panel pixels in the browser at six panel sizes, story states first (2026-10-28).
- [ ] PyPI release (`lightkeeper` and `lightkeeper-display` were both free on 2026-10-25).
- [ ] Contributor guide for other CGM and controller setups.
- [ ] First outside tester runs a display beside their primary app and reports back.

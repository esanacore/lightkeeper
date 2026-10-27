# MVP Backlog

The phased rollout of the whole stack. Phases gate on evidence, not dates. `TODO.md` holds individual work items.

## Phase 0: Foundation (this repository)

- [x] Bootstrap the repo with the engineering constitution.
- [x] Write the safety boundary, hazard log, and ADRs 0001 to 0005.
- [x] `lightkeeper` 0.1.0: parse, classify, render, degrade safely, with tests (FR-001 to FR-006).
- [ ] Kaitlin reviews `docs/SAFETY.md` and the default thresholds.

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
- [~] Raspberry Pi e-paper bedside display (FR-007), side by side with the primary app for one full sensor session. Done: the 1-bit rasterizer and the hardened systemd service with a watchdog. Next: the SPI panel driver once the parts arrive.
- [~] Home Assistant sensor and alerts (FR-008). Built over MQTT discovery (ADR-0010, HAZ-013) and tested against a fake broker; next, a check against a real Home Assistant (GAP-002).
- [x] ESP32 safety rules in C++ with shared-vector parity tests (ADR-0006).
- [ ] Xteink X4/X3 device build and side-by-side validation (FR-010).

## Phase 5: Companion App (ADR-0008)

- [~] Read-only iOS app: glance screen, settings, Keychain token, CI build (done); IOB, recent treatments, widgets, watch complication (next).
- [ ] Study LoopFollow's Trio Remote Control implementation; build a fake Trio endpoint for tests.
- [ ] Hazard analysis for the bolus request screen in `docs/SAFETY.md`.
- [ ] Bolus request screen, gated behind the promotion criteria in ADR-0008.

## Phase 6: Community

- [x] Publish the demo page (2026-10-24, https://esanacore.github.io/lightkeeper/).
- [ ] PyPI release (`lightkeeper` and `lightkeeper-display` were both free on 2026-10-25).
- [ ] Contributor guide for other CGM and controller setups.
- [ ] First outside tester runs a display beside their primary app and reports back.

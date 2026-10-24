# TODO

The living roadmap. The phased rollout plan is in `docs/MVP_BACKLOG.md`; this file tracks concrete work items.

## Features

From `docs/COMMUNITY_RESEARCH.md` (October 2026):

- [ ] Graded aging before STALE: mark a reading as aging between about 7 and 15 minutes so it never looks as fresh as a new one (needs a vector change and a hazard review).
- [ ] Distinguish "phone stopped uploading" from "Nightscout unreachable" using Nightscout device status.
- [ ] Night profile for displays: scheduled dimming, silent or haptic-only options, per-display quiet hours.
- [ ] Show delta from the previous reading, IOB and COB (greyed at zero), loop status, and "next reading in".
- [ ] Compression-low hint on a sudden single-interval drop, labeled as a hint.
- [ ] Firmware: exponential backoff on Wi-Fi, visible "offline since", published battery measurements (FR-015, reserved); study WaveshareMon's config schema before inventing one.
- [x] Extend the vector schema (`seconds_ago`, several entries per case, custom thresholds) so duplicate-timestamp, 15-minutes-plus-one-second, and custom-threshold cases become shared vectors (2026-10-23: 16 new cases, firmware `newest_reading`).
- [x] (2026-10-23, with a Linux CI job) Let `LightkeeperCore` build with the Windows and Linux Swift toolchains: guard `FoundationNetworking` in `NightscoutClient.swift` and replace the `kCFBooleanTrue` identity check, which only exists on Apple platforms. Then the vector tests can run outside macOS CI.
- [x] (2026-10-23: it checks inside WSL, since MinGW cannot link the sanitizers) `tools/doctor.py`: accept `mingw32-make` on Windows, or point at WSL, so a Windows machine with WinLibs passes.
- [ ] Check whether `lightkeeper` is free on PyPI before Phase 6; fallback name `lightkeeper-display`.
- [ ] iOS: unit tests for `Settings.load()` resetting an invalid set and for `reclassify()` yielding STALE without a fetch (needs a test target in `project.yml`).
- [ ] Evaluate Nightscout's `AUTH_DEFAULT_ROLES=denied` plus v3 JWT so the token never appears in a URL.

- [ ] Raspberry Pi e-paper display adapter for `lightkeeper` (FR-007).
- [ ] Home Assistant integration: publish level, value, and age as a sensor, alert on URGENT LOW and STALE (FR-008).
- [ ] Optional mmol/L display units (FR-013, reserved).
- [ ] Show a short sparkline or delta from the previous reading (FR-014, reserved).
- [ ] Draw `render_svg` output to a real e-paper bitmap for the Pi adapter (FR-007), reusing the gallery layout.

## Technical Debt

- [ ] The Nightscout v1 API takes the token as a query parameter. Evaluate the v3 API with JWT bearer auth so the token never appears in URLs or proxy logs.
- [ ] Upstream: the constitution's `constitution-env.yml` template calls `scripts/check_env_vars.sh` instead of `constitution/scripts/check_env_vars.sh`, so it silently skips in every adopter. Fixed locally; propose the fix in the engineering-constitution repo.
- [ ] Decide whether to keep the gstack section in `CLAUDE.md` (gstack is not installed in cloud sessions).

## Refactoring

- [ ] Split rendering profiles (terminal, e-ink 2.13", e-ink 4.2") once a second display exists.

## Testing

- [ ] GAP-001: hardware-in-the-loop check for the e-paper panel (FR-007).
- [ ] GAP-002: Home Assistant integration tests (FR-008).
- [ ] GAP-004: multi-day `--watch` soak test for memory growth and clock drift.
- [~] GAP-003: localhost fake Nightscout covers the HTTP layer; still need a real Nightscout instance.
- [ ] GAP-005: Xteink device build and on-hardware tests (FR-010).
- [ ] GAP-006: measure firmware coverage with gcov.

## Documentation

- [ ] Fill in exact Nightscout deployment steps once the hosting choice is made (`docs/SETUP.md`).
- [ ] Record Trio build and settings notes from the first build.
- [ ] Kaitlin reviews `docs/SAFETY.md` and the default thresholds.
- [x] Publish `demo.html` on GitHub Pages and link it from the README's Demo section (2026-10-24, `pages.yml`).
- [x] Add a version line to the README (approved and added 2026-10-24).

## Nice-to-Have

- [~] Xteink X4/X3 pocket display (ADR-0006): safety rules ported to C++ with host tests and shared vectors. Next: buy the device, add the PlatformIO ESP32-C3 project (Wi-Fi, HTTPS, JSON, e-paper, deep sleep).
- [ ] Decide CGM: stay on Dexcom G7 or move to FreeStyle Libre 3 Plus, which Trio reads directly with no vendor app (see ADR-0002). Kaitlin's call with her endo and insurance.
- [ ] Contribute test logs and bug reports upstream to Trio's Omnipod 5 driver (released in Trio v1.0.0).
- [ ] Revisit an Android collector with xDrip+ and AndroidAPS once AndroidAPS supports Omnipod 5.

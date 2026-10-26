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
- [x] Check whether `lightkeeper` is free on PyPI before Phase 6; fallback name `lightkeeper-display` (2026-10-25: both free; only publishing a release reserves a name, which is Eric's call).
- [x] iOS: unit tests for `Settings.load()` resetting an invalid set and for `reclassify()` yielding STALE without a fetch (2026-10-25: `LightkeeperTests` target, run on a simulator in CI).
- [x] Evaluate Nightscout's `AUTH_DEFAULT_ROLES=denied` plus v3 JWT so the token never appears in a URL (2026-10-25: ADR-0009 proposes the `api-secret` header on v1 instead; JWT is the fallback).
- [x] ADR-0009 accepted and implemented (2026-10-25): the Python and Swift clients send the readable token in the `api-secret` header, `?token=` is gone, and tests assert no request URL carries it.
- [ ] ADR-0009 real-instance check once Nightscout is deployed: with `AUTH_DEFAULT_ROLES=denied`, the header returns entries and no credentials return 401; record it in `docs/TEST_PLAN.md`.
- [ ] Firmware device HTTP layer (FR-010): send the token in the `api-secret` header, never in the URL (ADR-0009).

- [ ] Raspberry Pi e-paper display adapter for `lightkeeper` (FR-007).
- [ ] Home Assistant integration: publish level, value, and age as a sensor, alert on URGENT LOW and STALE (FR-008). ADR-0010 (proposed, 2026-10-25) recommends MQTT discovery with a standard-library publisher, Last Will, and `expire_after`, plus a `--json PATH` output; implement once Eric picks the transport and the hazard entry is written.
- [ ] Optional mmol/L display units (FR-013, reserved).
- [ ] Show a short sparkline or delta from the previous reading (FR-014, reserved).
- [x] Draw `render_svg` output to a real e-paper bitmap for the Pi adapter (FR-007), reusing the gallery layout (2026-10-25: `epaper_bitmap.py`, own 5x8 font, PNG preview and Waveshare buffer).
- [ ] Pi adapter, once the parts arrive: send `Bitmap.to_epd_buffer()` to the 2.9" Touch e-Paper HAT over SPI, confirm the buffer orientation on the real panel (GAP-001), and decide whether the panel shows a refresh-time stamp so a dead Pi cannot leave a fresh-looking screen.

## Technical Debt

- [x] The Nightscout v1 API takes the token as a query parameter. Evaluate the v3 API with JWT bearer auth so the token never appears in URLs or proxy logs (covered by ADR-0009).
- [~] (PR open: https://github.com/esanacore/engineering-constitution/pull/97, 2026-10-25) Upstream: the constitution's `constitution-env.yml` template calls `scripts/check_env_vars.sh` instead of `constitution/scripts/check_env_vars.sh`, so it silently skips in every adopter. Fixed locally; propose the fix in the engineering-constitution repo.
- [x] Decide whether to keep the gstack section in `CLAUDE.md` (kept, 2026-10-24).

## Refactoring

- [ ] Split rendering profiles (terminal, e-ink 2.13", e-ink 4.2") once a second display exists.

## Testing

- [ ] GAP-001: hardware-in-the-loop check for the e-paper panel (FR-007).
- [ ] GAP-002: Home Assistant integration tests (FR-008).
- [~] GAP-004: multi-day `--watch` soak test for memory growth and clock drift. Accelerated three-day soak in the suite (2026-10-25, `tests/test_soak.py`); still to do: a real multi-day run on the Pi once it exists.
- [~] GAP-003: localhost fake Nightscout covers the HTTP layer; still need a real Nightscout instance.
- [ ] GAP-005: Xteink device build and on-hardware tests (FR-010).
- [x] GAP-006: measure firmware coverage with gcov (2026-10-25: `make -C firmware/xteink coverage`, 100% lines, 113 of 114 branches).

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

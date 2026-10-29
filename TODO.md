# TODO

The living roadmap. The phased rollout plan is in `docs/MVP_BACKLOG.md`; this file tracks concrete work items.

## Decisions

Choices waiting on Eric (and Kaitlin where named). The code runs on the default shown until each is decided; other documents refer to these numbers.

- [ ] D1, brand additions (Eric): approve the Keeper's Logbook additions in `docs/BRAND.md` and `assets/brand/tokens.json`: Line strong, Beam text, the four chip tints, Band text, Night paper and Night ink, the Keeper 5x8 name, the textures, the hard shadow, and the pixel icons and marks, including the lamp shape (another lamp is fine); and the iOS accent color as Beam text (`#8C5800` light, `#E0A526` dark) instead of Beam. Default: the tokens are already used by iOS, the demo, the SVG panel and the terminal frame, labelled as awaiting approval. After approval, mirror them into `wiki/Brand.md`: the contrast column, a Keeper's Logbook section linking `docs/BRAND.md` and `assets/brand/tokens.json`, the pixel icon table with raw.githubusercontent URLs to `assets/brand/png/pixel-*@4x.png`, asset rows for `tokens.json`, `pixel-icons.json` and the pixel PNGs, the Band text row, and the Line and Beam role text.
- [ ] D2, IN RANGE on glance surfaces (Eric): should IN RANGE go neutral (Ink border, no green)? Default: IN RANGE keeps its green; neutral is written in `docs/BRAND.md` as proposed, not in use.
- [ ] D3, stamps (Eric): should physical panels show the `HH:MM` drawing-time stamp by default, and should the SVG stamp move from `written HH:MM UTC` to local time? Default: opt-in in the reference renderer (`render_bitmap` with `stamp=None`); `--png` and `--bmp` are always stamped with the local `HH:MM`; the SVG keeps `written HH:MM UTC`. If the SVG stamp changes, it changes together with the `docs/SAFETY.md` citation of `test_haz011_written_stamp_is_optional_and_utc`.
- [ ] D4, headline wrap on small panels (Eric; Kaitlin reviews the contact sheets): should the headline and long context lines wrap onto two rows on 200x200 and 250x122 panels? Default: no wrap; the small-panel exceptions are pinned by `test_fr007_small_panel_exceptions_are_pinned_pending_d4` (GAP-012).
- [ ] D5, spoken wording (Eric and Kaitlin): review the table that `python tools/gen_spoken_vectors.py --table` prints. Should "Nightscout unreachable." come before the confirm sentence instead of last? Is the STALE sensor-limit wording ("Stale, do not trust. Last reading below 40, 20 minutes ago. Confirm on the primary device.") acceptable? Default: STALE keeps the old number after the warning with no trend word; "Nightscout unreachable." comes last; speech keeps the confirm sentence even where the four-line STALE screen drops it; STALE sensor limits say "below 40" or "above 400".
- [ ] D6, ADR-0011 screen text v2 (Eric runs the hazard review, Kaitlin picks, both sign): run the hazard review for HAZ-017 to HAZ-019; Kaitlin picks c1 (round the age up) or c2 ("over N min ago", which needs the stale limit as a required render argument in all three languages); sign section 5 of `docs/SAFETY_REVIEW.md`; then implement it in one pull request at `spec_version` 2. Default: ADR-0011 stays Proposed, nothing in it is implemented, and `spec_version` stays 1.
- [ ] D7, graded aging (Eric and Kaitlin): add any aging cue before the stale cutoff? Default: none (ADR-0011's deferred list).
- [ ] D8, new screen text (Eric): allow new screen text in this batch? Default: no; `spec/display_vectors.json` is byte-identical at `spec_version` 1.
- [ ] D10, Apple signing (Eric): signing and App Groups for the widget extension and a TestFlight build. Default: no extension and no TestFlight build; only the glance timeline core exists.
- [ ] D11, firmware panel driver and TLS (Eric): a home-grown SSD16xx driver or GxEPD2 under GPL-3.0; approval to fetch the pinned CA certificate for the firmware networking step; the X4's panel controller confirmed on the bench. Default: no panel driver and no network code; the skeleton prints the panel over USB serial only.
- [ ] D13, font files (Eric): ship font files? Default: none ship (system font stacks; IBM Plex only if installed; the pixel font drawn on canvas).
- [ ] D14, status payload version (Eric): keep payload version 2 at the source (`age_minutes` null, never negative, for a future-dated reading; the new `reading_at`), or go back to version 1 and keep only the Home Assistant age-template guard? Default: version 2 (`PAYLOAD_VERSION = 2`). Going back means changing `status_payload.py`, `test_fr008_payload_version_is_2` and the vector test.
- [ ] D15, night profile (Eric): adopt it? Default: written in `docs/BRAND.md` as proposed, not in use; dark mode uses Night paper for panel previews only.
- [ ] D16, iOS Stale after cap (Eric and Kaitlin): lower it below 60 minutes? Default: the cap stays 60, with a caution above 15 minutes.
- [ ] D17, terminal pixel view (Eric): add a `--pixels` (Unicode half-block) view? Default: no.
- [ ] Coverage floor (Eric): confirm that NFR-004 itself moves from a 90% to a 100% line and branch floor. Default: `fail_under = 100` in `pyproject.toml` since wave 1, and the docs say 100%.
- [ ] The `--watch` footer note (Eric): keep the advice note drawn under the footer of the interactive frame while a failure lasts, or show only header, box and footer, with advice on stderr alone? Default: the note stays (plain ASCII, outside the box, never in piped, systemd or `--json` output); the stderr line is still written once per change.
- [ ] An upper bound for `LK_STALE_MINUTES` (Eric and Kaitlin), for example 60 like the iOS cap, under ADR-0011 or a hazard entry? Default: no upper bound; any positive whole number is accepted.
- [ ] `--panel` without `--png` or `--bmp` (Eric): exit 2, like the `--demo-*` options without `--demo`? Default: accepted, and it does nothing.
- [ ] SVG title separator (Eric): the title joins lines with ` / `, which collides with the FortyFiveUp arrow `/` (`high_181` reads "HIGH / 181 mg/dL / / 4 min ago"); use a different separator? Default: ` / `; `<desc>` carries one line per screen line.
- [ ] Stretched STALE headline in the SVG (Eric): is the stretch (a transform with four-decimal numbers, for example `matrix(1 0 0 1.0909 0 -1.2726)` at 296x128) acceptable in the generated gallery, or should STALE stay unstretched at 22 px? Default: stretched to the band height.
- [ ] The iOS URGENT band (Eric, on a device or TestFlight): approve a `.title` band whose minimum height is the scaled 96 pt number, so the band is the largest element while the fresh number stays the hero, or go back to the spec's `.title2` band and record the URGENT exception. Default: the `.title` band.
- [ ] Nightscout under a sub-path (Eric): iOS refuses a Nightscout address with a path while Python accepts one. Is that the intended difference, or should iOS allow a path that ends at the site root? Default: iOS refuses any path other than `/`; Python is unchanged.
- [ ] A non-color cue for LOW and HIGH chips on screens (Eric): IN RANGE, LOW and HIGH share the chip shape and differ only by word and border color; add one (for example a 2 px Ink rule under the LOW and HIGH chip) on iOS and the demo? Default: no extra rule; `docs/BRAND.md` says so plainly.
- [ ] The 32 px mark's grid (Eric): keep `mark-32` on a 32x32 grid, or force it onto 16x16 as the LK-01 spec said? Default: 32x32; icons are 16x16, and each mark is N x N for the N in its name.
- [ ] The panel layout's integer choices (Eric), before more ports lock them in: body cap `min(band, max(3, band // 2))`, stamp scale `max(2, h // 240)`, a 2 px minimum gap, a 2 px headline inset. Default: as implemented in Python, C++ and JavaScript; changing any of them bumps `panel_spec_version` and all three renderers.
- [ ] Glance timeline questions for the widget extension (Eric): is a 5-minute reload interval right against WidgetKit's budget? Should a reading already older than `maxMinutes` (default 120) keep aging for `maxMinutes` after now instead of giving one STALE frame frozen at its current age? Does a STALE widget show the struck `last:` line or no number? Default: a 5-minute interval, one frozen STALE frame, and STALE widget content left to the widget extension (text always from the lines).
- [ ] The demo's page weight (Eric): keep the exact self-referential weight (`pageBytes`, regenerated by `tools/gen_demo_panel.py` after any `demo.html` edit), or switch to a looser "under 100 KB" that a test bounds? Default: the exact weight; `tests/test_demo_panel.py` fails with the regeneration instruction if it is forgotten.
- [ ] A stale-colour rule on the demo's STALE banner (Eric): give the phone mock and chip the 4 px stale-colour leading rule the URGENT bands have? Default: no; the stale colour reaches it only through the hatched frame.
- [ ] Firmware panel buffer per board (Eric): size it per board (5,000 bytes on 200x200, 48,000 on 800x480) instead of the 60,000-byte cap from the profile list, which costs about 55 KB of static RAM on the bench board? Default: `kMaxPanelBytes` = 60,000.
- [ ] An LGPL note before distributing firmware binaries (Eric): the firmware statically links Arduino-ESP32 (LGPL-2.1-or-later); add a release-process note on relinking obligations now? Default: the OTS row records it as a Medium risk; no note yet, and no binaries are distributed.
- [ ] Hazard severity (Eric and Kaitlin): confirm in the hazard review the severity and likelihood set for HAZ-014 (Critical, Possible), HAZ-015 (Critical, Possible once widgets ship) and HAZ-016 (Serious, Possible), and review HAZ-014 to HAZ-016 with the log. Default: the rows are in `docs/SAFETY.md` with those values and a note that the review is pending.
- [ ] Where "phone quiet" goes (Eric): FR-015 keeps device status on hardware displays; the "phone quiet N min" idea ADR-0011 defers (uploader device status) has no ID until it is promoted. Default: FR-015 stays device status (COULD, Planned).

## Features

From `docs/COMMUNITY_RESEARCH.md` (October 2026):

- [ ] Graded aging before STALE: mark a reading as aging between about 7 and 15 minutes so it never looks as fresh as a new one (needs a vector change and a hazard review; ADR-0011 defers it; default: no aging cue before the cutoff, D7).
- [ ] Distinguish "phone stopped uploading" from "Nightscout unreachable" using Nightscout device status (the "phone quiet" idea deferred in ADR-0011; it gets its own requirement ID when promoted, FR-015 stays device status).
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
- [x] Firmware JSON layer (FR-010): `lib/nightscout_json`, heap-free and fuzzed, matched to Python by `spec/response_vectors.json` (2026-10-27).
- [ ] Firmware device HTTP layer (FR-010): send the token in the `api-secret` header, never in the URL (ADR-0009), and feed the body to `newest_reading_from_json`. Then, on the device: never `setInsecure`, keep the token only in NVS and the `api-secret` header, draw the stamp only with a trusted clock and a not-updating screen before sleep, and blank the panel when `render_panel` refuses (D11 picks the panel driver).
- [ ] Bench board (HUMAN, Eric): confirm the Waveshare ESP32-S3-ePaper-1.54's flash size and mode (8 MB qio and `default_8MB.csv` assumed; set `board_upload.flash_size`, `board_build.partitions` and `board_build.flash_mode` in `[env:bench_s3]` if they differ), then `cd firmware/xteink && pio run -e bench_s3 -t upload && pio device monitor -e bench_s3`: expect NO DATA / Nightscout unreachable and "crc32 3339447321 ... ink 2386" every minute, with Serial on native USB. Then check the schematics and fill in the pins and panel details in `src/device_config.h` before setting `kPinsVerified`.
- [ ] X4 (HUMAN): confirm the panel resolution, orientation and controller (800x480 landscape assumed), the 4 MB flash, and whether USB goes through the chip's USB Serial/JTAG (drop `ARDUINO_USB_MODE` for x4 if it uses a UART bridge) before flashing an X4.

- [ ] Raspberry Pi e-paper display adapter for `lightkeeper` (FR-007).
- [x] Home Assistant integration: publish level, value, and age as a sensor, alert on URGENT LOW and STALE (FR-008). Done 2026-10-26: ADR-0010 accepted, HAZ-013, standard-library MQTT publisher with Last Will and `expire_after`, unretained state, `--json PATH`.
- [ ] FR-008 against a real Home Assistant and Mosquitto: discovery creates the four sensors (including the Last reading timestamp), the example automations fire, and stopping the publisher makes the entities unavailable (GAP-002). Also check that the Last reading sensor shows unknown, not an error, on NO DATA, and that a level outside the enum's options is ignored.
- [ ] Optional mmol/L display units (FR-013, reserved).
- [ ] Show a short sparkline or delta from the previous reading (FR-014, reserved).
- [x] Draw `render_svg` output to a real e-paper bitmap for the Pi adapter (FR-007), reusing the gallery layout (2026-10-25: `epaper_bitmap.py`, own 5x8 font, PNG preview and Waveshare buffer).
- [ ] When the Pi panel driver lands, open the service sandbox just enough: replace `PrivateDevices=yes` with `DeviceAllow=` for `/dev/spidev0.0` and the GPIO chip, add `SupplementaryGroups=spi gpio`, and update `tests/test_deploy.py`.
- [ ] When the Pi and HAT arrive: measure the four VERIFY values in `hardware/enclosure/bedside.scad` (glass thickness, header gap, Pi offset, cable plug), print a test bezel, adjust, re-render with `python tools/render_enclosure.py`, and record the fit in `docs/TEST_PLAN.md`.
- [ ] Enclosures for the 7.5" across-the-room panel and a stand or sleeve for the Xteink X4 Pro, once those parts are chosen.
- [ ] Pi adapter, once the parts arrive: send `Bitmap.to_epd_buffer()` to the 2.9" Touch e-Paper HAT over SPI, confirm the buffer orientation on the real panel (GAP-001), and apply D3 (whether the physical panel shows the HH:MM stamp, HAZ-014).
- [ ] Widget, StandBy and Live Activity extension on `GlanceTimeline.swift` (needs D10): measure the reload cadence on a device (`reloadAfterMs` asks every 5 minutes, `glanceReloadIntervalMs`, against WidgetKit's roughly 40 to 70 reloads a day; tune it, for example to 15 minutes or the stale limit, before widgets ship); call `WidgetCenter.shared.reloadAllTimelines()` on each new reading and after a settings save; build the placeholder from `glanceTimeline(lastGood: nil, ...)`. Owner: Eric (needs a device). GAP-010.

## Technical Debt

- [x] The Nightscout v1 API takes the token as a query parameter. Evaluate the v3 API with JWT bearer auth so the token never appears in URLs or proxy logs (covered by ADR-0009).
- [x] (Merged 2026-10-26: https://github.com/esanacore/engineering-constitution/pull/97; re-pin `constitution/` at the next constitution release) Upstream: the constitution's `constitution-env.yml` template calls `scripts/check_env_vars.sh` instead of `constitution/scripts/check_env_vars.sh`, so it silently skips in every adopter. Fixed locally; propose the fix in the engineering-constitution repo.
- [x] Decide whether to keep the gstack section in `CLAUDE.md` (kept, 2026-10-24).
- [ ] Add `tools` to `[tool.mypy] files` in `pyproject.toml` so the generators are type-checked in CI (`tools/gen_brand_pixels.py` is already strict-clean; check the others).
- [ ] `src/lightkeeper/config.py` uses the literal "lightkeeper" for the default `LK_MQTT_NODE_ID`; use `home_assistant.DEFAULT_NODE_ID` so a default install can never get the suffixed device name by accident.
- [ ] Export `assets/brand/png/app-icon.png` at 1024 px from `assets/brand/app-icon.svg` (or add a `tools/` generator), then copy it over `apps/ios/Lightkeeper/Sources/Assets.xcassets/AppIcon.appiconset/app-icon.png`; today the catalog icon is the 512 px PNG doubled by a script that is not in the repository (`test_nfr005_app_icon_is_the_brand_icon_at_1024` accepts either).
- [ ] `tests/test_soak.py` on CPython 3.14 (Windows): memory traced to `src/lightkeeper` grows 0.3 to 2.1 KB in every 335-cycle window even after `gc.collect()` (mostly the stamp's `strftime` in `svg_display.py` and the `isoformat` in `status_payload.py`, and the base branch shows it too), so the second-window limit is 16 KB, only about 2% under the smallest real leak (about 16.7 KB). Find the creep or measure a different signal, such as object counts. CI runs 3.11 on Linux.
- [ ] Firmware: an optimized host build (-O2 with MinGW g++ 16) would fail -Werror on format-truncation at `glucose_rules.cpp:28` and a false-positive maybe-uninitialized for `value_lines` and `age_lines` at `panel_bitmap.cpp:255-256`; zero-initialize those arrays and widen the buffer if an optimized build is ever added (CI builds at -O0; PlatformIO's -Os prints none).

## Refactoring

- [x] Split rendering profiles once a second display exists (2026-10-27: `panel_profiles.py` holds six panel sizes; 2026-10-28: the terminal frame is `terminal_view.py`).
- [ ] `firmware/xteink/test/host/test_panel_bitmap.cpp` is 702 lines, over the 600-line advisory: a later change could move the serial-dump tests into `test/host/test_serial_panel.cpp` with its own Makefile target and the generated `panel_vectors.inc`.
- [ ] Advisory size signals: `tests/test_brand_tokens.py` (706 lines), `tests/test_svg_display.py` (614), `tests/test_demo_panel.py` (762) and `web/panel/panel.js` (670); look, but split only for a reason beyond length.

## Testing

- [ ] GAP-001: hardware-in-the-loop check for the e-paper panel (FR-007).
- [~] GAP-002: Home Assistant integration tests (FR-008). Fake-broker tests cover the protocol, now four sensors, and every HAZ-013 mitigation (2026-10-26); a real Home Assistant check remains.
- [~] GAP-004: multi-day `--watch` soak test for memory growth and clock drift. Accelerated three-day soak in the suite (2026-10-25, `tests/test_soak.py`); still to do: a real multi-day run on the Pi once it exists. See the soak item under Technical Debt.
- [~] GAP-003: localhost fake Nightscout covers the HTTP layer; still need a real Nightscout instance.
- [~] GAP-005: Xteink device build and on-hardware tests (FR-010). Done 2026-10-28: the panel rasterizer at pixel parity and a build-only skeleton whose NO DATA screen and serial dump are host-tested. Next: Wi-Fi, TLS, the panel driver (D11) and the dump on a real board.
- [x] GAP-006: measure firmware coverage with gcov (2026-10-25: `make -C firmware/xteink coverage`, 100% lines, 113 of 114 branches).
- [ ] GAP-007: an icon that resembles a trend arrow is caught only by the `docs/BRAND.md` checklist; consider a mechanical check.
- [ ] GAP-008 (HUMAN): run `python -m lightkeeper --demo --watch` in Windows Terminal and on a Pi over SSH; confirm the frame redraws in place with no scrollback growth, Ctrl+C leaves the terminal colors normal, and `--no-color` keeps underline and reverse.
- [ ] GAP-009 (HUMAN, Eric, device or TestFlight, D10): after the `ios.yml` jobs core-tests, core-tests-linux and app-build are green (app-build is the first compile of the rebuilt SwiftUI views), look at the glance at default size and AX5 in light and dark for IN RANGE, LOW, URGENT, STALE, NO DATA and the setup card, confirm the icon on the home screen, and with VoiceOver confirm the glance reads as one sentence group.
- [ ] GAP-010: the widget extension and its reload cadence (see Features).
- [ ] GAP-011 (HUMAN): on a real Windows laptop at 125% and 150% scaling, open `demo.html` and zoom into the panel to confirm even stroke widths (headless emulation cannot show device-pixel snapping at the canvas edges).
- [ ] GAP-012: small-panel exceptions at 200x200 and 250x122 wait on D4.
- [ ] Demo look (HUMAN, Eric): review `demo.html`'s phone mock sizing (the banner over the number) and the colophon wording.
- [ ] Four `tests/test_cli.py` tests fail now and then on a loaded Windows machine (CPython 3.14) and pass on rerun. `test_fr006_ctrl_c_watch_exits_0_and_marks_ha_offline` (about 1 in 5 runs alone), `test_fr006_ctrl_c_mid_fetch_in_watch_still_marks_ha_offline` and `test_fr006_ctrl_c_one_shot_after_a_publish_leaves_ha_available`: the fake broker's `wait_for` returns, or times out after 5 s, before the last packets (OFFLINE, DISCONNECT) arrive; wait for DISCONNECT itself, or allow longer. `test_fr006_demo_values_all_apply`: it printed `1 min ago` for a reading built 2 minutes before now, which only a wall clock stepping backwards explains; pin a fixed clock.
- [ ] First CI runs on the pull request (AUTOMATED): `firmware-device.yml` (never run yet), the Constitution Test Runner (the first Linux g++ ASan run of `panel_tests` and the first run of the POSIX-only `test_haz014_stamp_and_header_are_local_time_never_utc`), and all three `ios.yml` jobs.

## Documentation

- [ ] Fill in exact Nightscout deployment steps once the hosting choice is made (`docs/SETUP.md`).
- [ ] Record Trio build and settings notes from the first build.
- [ ] Kaitlin reviews `docs/SAFETY.md` (including HAZ-014 to HAZ-016) and the default thresholds, signs the ADR-0011 section of `docs/SAFETY_REVIEW.md` (D6), and looks at the before/after panel contact sheets at six sizes before a bedside panel is relied on (the sheets are not in the repository; attach them to the pull request). One trade-off to look at: at 296x128 the IN RANGE screen with `Nightscout unreachable` draws the number at scale 3 instead of 4 so the age keeps scale 3.
- [x] Publish `demo.html` on GitHub Pages and link it from the README's Demo section (2026-10-24, `pages.yml`).
- [x] Add a version line to the README (approved and added 2026-10-24).

## Nice-to-Have

- [~] Xteink X4/X3 pocket display (ADR-0006): safety rules, the JSON parser and the panel rasterizer in C++ at parity with Python, and a build-only PlatformIO skeleton for the bench ESP32-S3 and the X4 that prints the NO DATA panel over USB serial (2026-10-28). Next: buy the device; Wi-Fi, HTTPS, the panel driver (D11), deep sleep with real data.
- [ ] Decide CGM: stay on Dexcom G7 or move to FreeStyle Libre 3 Plus, which Trio reads directly with no vendor app (see ADR-0002). Kaitlin's call with her endo and insurance.
- [ ] Contribute test logs and bug reports upstream to Trio's Omnipod 5 driver (released in Trio v1.0.0).
- [ ] Revisit an Android collector with xDrip+ and AndroidAPS once AndroidAPS supports Omnipod 5.

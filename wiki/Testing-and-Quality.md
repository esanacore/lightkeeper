# Testing and Quality

How the repository is tested, what it promises about coverage, and how a reader can check those promises. The source documents are `docs/TEST_PLAN.md`, `docs/REQUIREMENTS_TRACEABILITY.md`, and `docs/PRODUCT_REQUIREMENTS.md` in the repository. Numbers are from the current tree (2026-10-28): 2,090 Python tests pass (2 more skip on Windows) at 100% line and branch coverage, 39 shared vectors, 237 panel vectors, 294 + 2,970 + 2,744 firmware checks, 75 Swift package tests, 14 Node tests, and for the Android app 82 JVM unit tests and 39 instrumented tests, plus 55 checks in `tests/test_android.py` that run with the Python suite.

## The pyramid

| Layer | What it covers | Where |
| --- | --- | --- |
| Unit | Domain rules with a fixed clock and plain data | `tests/test_glucose.py`, `tests/test_status.py` |
| Integration | Nightscout client against an injected fetcher, application layer against fakes, CLI end to end in demo mode | `tests/test_nightscout.py`, `tests/test_monitor.py`, `tests/test_cli.py` |
| HTTP integration | A fake Nightscout on localhost exercises the real urllib fetcher: status codes, timeouts, oversized bodies, HTML pages, redirects | `tests/test_http_integration.py` |
| Shared vectors | Every case in `spec/display_vectors.json`, run by Python, C++, and Swift | `tests/test_vectors.py`, `firmware/xteink/test/host/`, `apps/ios/LightkeeperCore/Tests/` |
| Panel pixels | Every display vector's 1-bit panel at six sizes, by CRC-32, in Python, C++ and the demo's JavaScript port | `tests/test_panel_vectors.py`, `firmware/xteink/test/host/test_panel_bitmap.cpp`, `web/panel/panel.test.mjs` |
| Spoken form | One screen-reader sentence per vector, in Python and Swift | `tests/test_spoken.py`, `SpokenVectorTests` |
| Brand tokens | Every surface's colors against `assets/brand/tokens.json`, the desktop window's and the Android app's included | `tests/test_brand_tokens.py`, `tests/test_ios_palette.py`, `tests/test_demo_panel.py`, `tests/test_tk_window.py`, `tests/test_ppm.py`, `tests/test_android.py`, `ColorDriftTest` |
| Citation guard | The hazard log and traceability matrix cite only tests that exist | `tests/test_safety_doc.py` |
| Terminal frame | Golden `--watch` frames for every vector, ASCII only, no bell | `tests/test_terminal_view.py` |
| Desktop window | Fake clock, FakeTk and three real-Tk checks: STALE on time with no fetch, jumps, the watchdog, the fit to the screen, the stamp, no bell or flash | `tests/test_glance.py`, `tests/test_tk_window.py`, `tests/test_desktop.py`, `tests/test_ppm.py` |
| Firmware host tests | C++17 rules, response parser, and panel rasterizer under AddressSanitizer and UBSan on a PC | `make -C firmware/xteink test` |
| iOS core tests | XCTest on Windows, and on GitHub's macOS and Linux runners | `.github/workflows/ios.yml` |
| iOS app layer | Settings and the model on an iOS simulator | `ios.yml` app-build |
| Android JVM | Address check, thresholds, request shape, captions, color drift, glance anatomy over every vector, the controller's timing | `apps/android/app/src/test/` (`./gradlew testDebugUnitTest`) |
| Android instrumented | Every display, response and panel vector through JNI on a device or emulator, the screen, settings and token store | `apps/android/app/src/androidTest/` (`./gradlew connectedDebugAndroidTest`, `android.yml`) |
| Android checks in pytest | Manifest, cleartext, colors, CMake by path, wrapper checksum, workflow pins | `tests/test_android.py` |
| Device build | Both ESP32 boards build with zero warnings | `.github/workflows/firmware-device.yml` |
| Gallery and demo | Committed `docs/DISPLAY_STATES.md`, SVGs, and demo table match the generator; the demo page stays one file that loads nothing and never moves | `tests/test_gallery.py`, `tests/test_demo_panel.py` |
| Static analysis | ruff (pycodestyle, pyflakes, import order, PEP 257, bugbear, pyupgrade, bandit), ruff format, strict mypy on `src/`, clang-format | pre-commit and CI |
| End to end | A real self-hosted Nightscout with simulated uploads | planned, GAP-003 |
| Manual validation | A display beside the primary app for one full sensor session, logging any mismatch, freeze, or missed STALE | before anyone relies on a display |

Test names carry the requirement or hazard ID they verify, for example `test_fr003_staleness_beats_urgent_low` or `test_haz011_one_poisoned_entry_never_hides_the_good_ones`, so `pytest -k fr003` runs everything for FR-003. That naming is the mechanism behind traceability.

## Shared vectors and three-way parity

`spec/display_vectors.json` holds 39 cases. Each is either one raw Nightscout entry (or none) with its age in `minutes_ago` or `seconds_ago`, or an `entries` list in which every entry has its own age, so the same file covers the 15-minutes-plus-one-second boundary, same-timestamp ties, poisoned entries next to good ones, and newest-wins selection. A case can also carry custom `thresholds`. Each gives an optional fetch error and the exact expected level and lines. The file carries a `spec_version` (currently 1) that increments whenever an existing case changes; adding a case or an optional field does not bump it.

Three suites run every case, must produce identical output, and assert the spec version: `tests/test_vectors.py` (Python), the firmware host tests (C++, with the vectors compiled into a header by the Makefile), and `VectorTests.swift`. This is FR-009 for Python and C++ and FR-012 for Swift. The Android app adds no fourth implementation: its instrumented `NativeVectorTest` runs every case through the firmware's C++ over JNI and asserts `spec_version` too (FR-020). Parity is enforced by tests rather than by discipline, and the vectors have caught real divergences: Python once rendered five lines for STALE while Nightscout was unreachable (`stale_while_unreachable_stays_four_lines`), and the firmware once passed a NaN through a cast by luck (`huge_value_rejected`, HAZ-011). Pictures are in [[Display States]].

Two more files follow the same pattern. `spec/panel_vectors.json` pins the 1-bit panel of every display vector at each of the six panel sizes, plus 3 stamped cases, 237 in all, each by the CRC-32 and ink count of its packed rows; it has its own `panel_spec_version` (currently 1). Three renderers must draw every case pixel for pixel: the Python reference, the C++ `panel_bitmap` in the firmware, and the demo's JavaScript port (`web/panel/panel.js`). This is FR-016. The Android app draws every case through the C++ `render_panel` over JNI, and the desktop window shows the Python reference's own pixels (FR-018). `spec/spoken_vectors.json` holds the one sentence a screen reader speaks for each display vector, shared by Python and Swift (FR-017); `python tools/gen_spoken_vectors.py --check` fails when it drifts from the code, and `--table` prints the wording for review. `python tools/gen_panel_spec.py --check` does the same for the panel vectors.

## Coverage floors

| Scope | Metric | Floor | Current |
| --- | --- | --- | --- |
| Repository default | Line and branch | 100% (`fail_under` in `pyproject.toml`) | 100% |
| Domain layer (the safety rules) | Line and branch | 100% | 100% |
| Nightscout client | Line and branch | 100% | 100% |
| Firmware `nightscout_json` | Every response case, edge cases, fuzzing | 100% of cases | 2,970 checks pass, 100% of lines |
| Firmware `glucose_rules` | Every shared vector plus edge cases | 100% of vectors | 294 checks pass; 100% of lines and 113 of 114 branches (gcov) |
| Firmware `panel_bitmap` | Every panel vector plus extra cases, sizes and stamps | 100% of the 237 panel vectors | 2,744 checks pass; 100% of lines (gcov) |
| Android app (Kotlin) | Line and branch | Not measured yet (GAP-014) | Every display, response and panel vector through JNI; pure logic in 82 JVM tests, the views in 39 instrumented tests |

Firmware coverage is measured with gcov: `make -C firmware/xteink coverage` reports 100% of lines and 113 of 114 branches in `glucose_rules.cpp`; the one branch left is a defensive guard that the public API cannot reach. It also reports 100% of the lines in `panel_bitmap.cpp` and in the device skeleton's `src/serial_panel.cpp`. The coverage history is a dated table in `docs/TEST_PLAN.md`.

## Requirements traceability

`docs/PRODUCT_REQUIREMENTS.md` defines each requirement with a stable ID, a MUST/SHOULD/COULD/WON'T level, and numbered acceptance criteria such as `FR-003-AC-2`. `docs/REQUIREMENTS_TRACEABILITY.md` maps each to its verifying tests and a status. Twenty declared requirements are Verified: FR-001 to FR-006, FR-008, FR-009, FR-011, FR-012, FR-016 (panel pixels), FR-017 (spoken form), FR-018 (the desktop window), FR-019 (the glance timeline core), FR-020 (the Android app) and NFR-001 to NFR-005 (NFR-005 is the brand tokens). FR-007, FR-010, FR-013, FR-014 and FR-015 are reserved in a Planned section and get rows when their first test lands. A constitution check fails the build if a declared requirement has no verifying test, which is why unstarted work is kept out of the declared list.

The gap log names what is not yet tested: GAP-001 physical e-paper output, GAP-002 a real Home Assistant check (fake-broker tests already run), GAP-003 a real Nightscout instance, GAP-004 a real-time multi-day `--watch` run on the Pi (an accelerated three-day soak already runs in the suite), GAP-005 the Xteink device build (High; partly closed on 2026-10-28 by the panel rasterizer and a build-only skeleton, while Wi-Fi, TLS, the panel driver and a run on a real board stay open). GAP-006, firmware coverage measurement, was closed on 2026-10-25.

Six gaps were added with the Keeper's Logbook work. GAP-007: a pixel icon that looks like a trend arrow is caught only by the review checklist in `docs/BRAND.md`, not by a test. GAP-008: the interactive `--watch` frame has not been seen in a real terminal (Windows Terminal, a Pi over SSH). GAP-009: the iOS app has not run on a device (Dynamic Type, light and dark, VoiceOver, the app icon); its reworked views and app tests first compiled and passed in CI, on a simulator, on the push to `main` at commit `1c0cdb8`. GAP-010: no WidgetKit extension uses the glance timeline yet, and its reload cadence against WidgetKit's daily budget is unmeasured. GAP-011: the demo panel at 125% and 150% display scaling has been checked only in a headless browser, not on real hardware. GAP-012: the 200x200 and 250x122 panels draw their longest lines at scale 1, the smallest, pinned as exceptions until a decision on wrapping the headline.

Three more came with the desktop window and the Android app. GAP-013: the Android app on a phone. No real phone (API 26 to 36) has run it, nor TalkBack or the API 26 navigation bar on a device; in CI all 39 instrumented tests pass, on an emulator only. GAP-014: Kotlin line and branch coverage is not measured; the pure logic is covered by JVM tests and the views by instrumented tests. GAP-015: the desktop window on macOS (whether the panel stays sharp on a Retina display), on Linux with a display (several monitors), and with the system clock set back by hand.

## The constitution CI checks

The repository adopts Eric's Engineering Constitution as a submodule, and its workflows run on every push and pull request: `constitution-tests.yml` runs the declared suite; `constitution-architecture.yml` verifies that layer dependencies point inward; `constitution-compliance.yml` checks governance files, a self-contained `demo.html`, the README's structure, and requirements traceability; `constitution-env.yml` checks `.env.example` and `docs/ENV_VARS.md` against the code; `constitution-secrets.yml` sweeps for secrets; `constitution-ots.yml` checks the OTS inventory; `constitution-doc-freshness.yml` flags source changes without documentation changes; `constitution-version.yml` checks the submodule is current; `constitution-wiki.yml` checks this wiki for dangling links and orphans and publishes it on merge. `ios.yml` builds and tests the Swift package on macOS and Linux runners, builds the app, and runs its tests on an iOS simulator; it also runs on a change to `assets/brand/tokens.json`. `firmware-device.yml` builds the ESP32 skeleton for both boards and fails on any warning. `android.yml` builds the Android debug APK, runs its JVM unit tests and lint, then its instrumented tests on an API 36 emulator with a Pixel 6 screen; it also runs on a change to the firmware libraries, the spec vectors or the brand tokens. The test runner sets up Node 24 for the demo's panel tests. Actions are pinned by commit SHA.

On the push of the Keeper's Logbook work to `main` (commit `1c0cdb8`), every constitution check passed, including the full suite on Linux, and `ios.yml` (the reworked views and app tests on the simulator) and `firmware-device.yml` passed for the first time. `android.yml`'s build, unit tests and lint passed too, and 38 of its 39 instrumented tests; the 39th failed only because the default emulator screen is too narrow for the panel. The workflow now uses a Pixel 6 screen, and on the next push (commit `5113fb5`) all 39 passed and `android.yml` was green.

## How to run everything

```bash
python tools/doctor.py
python -m ruff check . && python -m ruff format --check . && python -m mypy
python -m pytest --cov --cov-report=term-missing
make -C firmware/xteink format-check test
node --test web/panel/panel.test.mjs
(cd apps/android && ./gradlew assembleDebug testDebugUnitTest lint)   # needs JDK 17 or 21 and the Android SDK
(cd apps/android && ./gradlew connectedDebugAndroidTest)             # with a phone or emulator attached
bash constitution/scripts/run_declared_tests.sh .
bash constitution/scripts/check_compliance.sh --product .
bash constitution/scripts/check_wiki_links.sh --strict .
```

## The mutation check

Coverage says a line ran, not that a test would notice if it were wrong. For the firmware rules a mutation check was done by hand and recorded in `docs/OTS_SOFTWARE.md` (OTS-106): a staleness comparison was deliberately broken and the host tests failed. There is no automated mutation tool. To repeat it on any implementation, flip one comparison in `classify` (`>=` for `>` on the stale check, or drop the future-skew branch), confirm the boundary vectors (`fresh_at_15_minutes`, `stale_at_16_minutes`, `small_clock_skew_ok`, `future_dated`) fail, then revert. A rule that does not fail at least one vector when mutated needs a new vector.

The Keeper's Logbook work added deliberate-bug checks: six on the spoken form, 25 on the glance timeline, and 17 on the firmware's serial dump. The suite caught every one that changes behavior; one equivalent glance-timeline mutant survives by design. The Android app got six deliberate bugs in the controller's timing, each caught by a JVM test, and two on the device (the Keystore's busy case and Save's check for an untouched token field), each caught by exactly the instrumented test meant to catch it. The desktop window's fix for a clock set back was checked the other way round: with Tk's own timer stalled, the reading arrives through the ticker thread alone, and with the ticker stubbed out the same run stays on NO DATA, as it should.

See [[Contributing]] for what a change must bring with it, and [[Safety]] for the hazards each test defends.

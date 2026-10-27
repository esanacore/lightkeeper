# Test Plan

This document defines how this repository is tested, what coverage it targets, and where coverage gaps currently exist.

## Test Strategy

- **Unit tests**: domain rules (parsing, thresholds, staleness) with a fixed clock and plain data. Location: `tests/test_glucose.py`, `tests/test_status.py`. Command: `python -m pytest tests/test_glucose.py tests/test_status.py`.
- **Integration tests**: the Nightscout client against an injected fetcher, the application layer against fake sources, and the CLI end to end in demo mode. Location: `tests/test_nightscout.py`, `tests/test_monitor.py`, `tests/test_cli.py`.
- **HTTP integration tests**: a fake Nightscout served on localhost exercises the real urllib fetcher, status codes, timeouts, and bad payloads. Location: `tests/test_http_integration.py`.
- **Shared response corpus (parity)**: `spec/response_vectors.json` holds raw Nightscout response bodies and the conclusion every implementation must reach (newest reading, no reading, or an error). Run by `tests/test_response_vectors.py`, the firmware's `test_nightscout_json.cpp` (with a deterministic fuzz pass of about 17,600 mutated bodies), and Swift's `ResponseVectorTests`. Regenerate it with `python tools/gen_response_corpus.py`.
- **Shared vectors (parity)**: `spec/display_vectors.json` is run by `tests/test_vectors.py` and by the firmware host tests, and by the Swift package tests on macOS runners, so Python, C++, and Swift render identical screens.
- **iOS core tests**: `LightkeeperCore` runs the shared vectors with XCTest on GitHub's macOS runners (`.github/workflows/ios.yml`), so the Swift rules stay identical too. Location: `apps/ios/LightkeeperCore/Tests/`.
- **Firmware host tests**: C++17 rules built with AddressSanitizer and UBSan, run on a PC. Coverage: `make -C firmware/xteink coverage` (gcov, Linux or WSL). Location: `firmware/xteink/test/host/`. Command: `make -C firmware/xteink test`.
- **End-to-end tests**: against a real self-hosted Nightscout instance with simulated uploads, planned once Nightscout is stood up (see GAP-003).
- **Static analysis**: ruff (pycodestyle, pyflakes, import order, PEP 257 docstrings, bugbear, pyupgrade, bandit security rules), ruff format, strict mypy on `src/`, and clang-format for the firmware. Run in the full suite and as pre-commit hooks.
- **Manual validation**: before anyone relies on any display, run it side by side with the primary app for at least one full sensor session and log any mismatch, freeze, or missed STALE.

## How to Run Tests

- Full suite: `python -m ruff check . && python -m ruff format --check . && python -m mypy && python -m pytest --cov && make -C firmware/xteink format-check test`
- Lint, format, and types only: `python -m ruff check . && python -m ruff format --check . && python -m mypy`
- With coverage: `python -m pytest --cov --cov-report=term-missing`
- A single test or subset: `python -m pytest -k fr003`

## Coverage Targets

| Scope | Metric | Floor |
| --- | --- | --- |
| Repository default | Line + branch | 90% |
| Domain layer (safety rules) | Line + branch | 100% |
| Nightscout client (credentials, untrusted input) | Line + branch | 95% |
| Firmware `glucose_rules` | Every shared vector + edge cases | 100% of vectors; 100% of lines and 113 of 114 branches by gcov (the one left is a defensive guard unreachable through the public API) |

## Continuous Coverage Evaluation

| Date | Overall coverage | Notes |
| --- | --- | --- |
| 2026-10-18 | 100% Python line and branch; firmware 153 checks under ASan/UBSan | 158 Python tests incl. HTTP integration, wiki guards, and 23 shared vectors; Swift vector and parse tests on macOS CI. Added after the adversarial review: HAZ-011 poisoned-entry isolation and watch-loop resilience, HAZ-012 Swift bounds. Gaps unchanged except GAP-003 partial. |
| 2026-10-23 | 100% Python line and branch; firmware 287 checks under ASan/UBSan | 175 Python tests and 39 shared vectors. The vector schema gained `seconds_ago`, multi-entry `entries`, and custom `thresholds`; second-level staleness and future-skew boundaries, same-timestamp ties, poisoned entries, and custom thresholds are now checked in all three implementations. The firmware gained `newest_reading` to match Python's `parse_entries`. Gaps unchanged. |
| 2026-10-23 (later) | 100% Python line and branch | 177 Python tests. `LightkeeperCore` now builds and passes its tests with the Windows Swift 6.4 toolchain, and a Linux job (`swift:6.1-noble`) in `ios.yml` keeps it portable; a JSONSerialization boolean test covers the real parse path on every platform. `tools/doctor.py` checks WSL for the firmware toolchain on Windows. |
| 2026-10-25 | 100% Python line and branch | First iOS app-layer tests: `LightkeeperTests` (9 tests) runs on a simulator in `ios.yml`, covering settings reset on invalid stored thresholds (HAZ-006, HAZ-012) and foreground re-classification to STALE without a fetch (HAZ-008). `GlucoseModel` takes an injectable clock and fetch, and `Settings` an injectable `UserDefaults`. |
| 2026-10-25 (later) | 100% Python line and branch | ADR-0009: the token moved from `?token=` to the `api-secret` header. Python: 182 tests, including that no request URL or request line carries the token, that the header survives a same-site redirect, and that a missing token is refused like `AUTH_DEFAULT_ROLES=denied`. Swift: `NightscoutClientTests` (5) cover the request shape and the redirect rule. Still open: the real-instance check (GAP-003). |
| 2026-10-25 (gcov) | Firmware `glucose_rules.cpp`: 100% of 120 lines, 113 of 114 branches taken (was 98.3% and 93.0%) | GAP-006 closed: `make coverage` added. New host tests cover the threshold-ordering branches, out-of-range enum fallbacks, a status with a level but no reading (renders NO DATA), and the tie-break with the lower value listed first. 294 checks. The untaken branch is the `set_line` overflow guard, unreachable through `render`. |
| 2026-10-25 (bitmap) | 100% Python line and branch | FR-007 groundwork: `tests/test_epaper_bitmap.py` (52 tests) checks that the font covers printable ASCII on a fixed 5x8 grid, that every shared vector rasterizes inside the panel margins with real glyphs at body scale 2 or more, that a narrowed headline stays taller than body text, the PNG encoding, and the Waveshare portrait buffer layout. 234 Python tests. Buffer orientation on a real panel stays open (GAP-001). |
| 2026-10-25 (soak) | 100% Python line and branch | GAP-004, accelerated: `tests/test_soak.py` runs 4,320 cycles (three days at 60 s) through `cli.main --watch --svg` with a fake clock in about 6 s. Memory is compared over two equal windows of about 2,000 cycles: standard-library caches warm up in the first (7 to 25 KB depending on platform), and Lightkeeper's own allocations must grow by under 8 KB in the second (measured 0.4 KB on Linux, 1.2 KB on Windows); a planted leak in the loop fails it at about 400 KB. Scheduling jitter does not drift the displayed age, a 40-cycle outage ages into STALE and recovers, and a 20-minute backwards clock step mid-outage shows STALE. 235 Python tests. Still open: a real multi-day run on the Pi (OS-level memory, real clock). |
| 2026-10-26 | 100% Python line and branch (712 statements, 196 branches) | FR-008: `tests/test_mqtt.py` (39) covers packet encoding against the spec's examples, CONNACK handling, TLS wrapping, plain MQTT refused off localhost, and password redaction; `tests/test_home_assistant.py` (27) runs the publisher against a fake broker on a real socket: will, retained discovery and availability, unretained state, reconnect, offline on watch exit, no number when STALE or a sentinel; CLI tests cover `--json`, the `LK_MQTT_*` settings, and a publish failure that never stops the display. Mutations that retain state or publish a number while STALE fail the tests. 313 Python tests. |
| 2026-10-27 | 100% Python line and branch (753 statements, 206 branches) | Service and watchdog: `tests/test_deploy.py` (17) checks `deploy/lightkeeper.service` against the real CLI parser (watchdog headroom, SIGINT stop, runtime-directory outputs, sandboxing keys) and the sd_notify messages with a fake sender, plus a real Unix datagram on Linux (skipped on Windows). `systemd-analyze verify` passes and `systemd-analyze security` reports 1.2 (checked in WSL, systemd 261). 329 Python tests. |
| 2026-10-27 (packaging) | 100% Python line and branch | `tests/test_packaging.py` builds the real wheel offline and checks that every module under `src/lightkeeper` ships, the `lightkeeper` console script points at `cli:main`, and there is no runtime dependency (ADR-0005). Mutations that rename the entry point or add a runtime dependency fail it. A clean-venv install of the wheel ran `lightkeeper --version`, `--demo`, and `--json`. 331 Python tests (one Linux-only). |
| 2026-10-27 (responses) | 100% Python line and branch; firmware `nightscout_json.cpp` 100% of 257 lines, 97% of branches | FR-010 groundwork: the firmware's heap-free Nightscout JSON parser and the shared response corpus (39 cases) run by Python, C++, and Swift. The firmware suite adds 2,970 checks, including a fuzz pass of 17,600 mutated bodies under ASan and UBSan with no crash. Swift on Windows found two cases where Foundation's JSON parser differs from Python's (a number it cannot represent, a trailing comma); both are syntax Nightscout never sends, and the corpus records them as safe Swift-only alternatives. 372 Python tests. |
| 2026-10-17 | 100% (269 statements, 68 branches) | Baseline, 87 tests |
| 2026-10-17 | 100% Python (271 statements, 70 branches); firmware 141 checks | 117 Python tests incl. HTTP integration and 22 shared vectors; C++ host tests under sanitizers. Firmware line coverage not yet measured (GAP-006). |

## Coverage Gap Log

| Gap ID | Area / behavior | Risk | Related requirement | Status | TODO ref |
| --- | --- | --- | --- | --- | --- |
| GAP-001 | Physical e-ink panel output | Medium | FR-007 | Open | TODO.md, Testing |
| GAP-002 | Home Assistant publishing | Medium | FR-008 | Partly closed 2026-10-26: fake MQTT broker tests; a real Home Assistant check remains | TODO.md, Testing |
| GAP-003 | End-to-end against a real Nightscout instance (localhost fake now covers the HTTP layer) | Medium | FR-001, FR-005 | Partially closed | TODO.md, Testing |
| GAP-004 | Long-running `--watch` soak test (memory, clock drift over days) | Medium | FR-005, FR-006 | Partly closed 2026-10-25: `tests/test_soak.py` runs three simulated days through the real loop; a real-time run on the Pi remains | TODO.md, Testing |
| GAP-005 | Xteink device build: Wi-Fi, TLS, JSON extraction, e-paper drawing | High | FR-010 | Open | TODO.md, Testing |
| GAP-006 | Firmware line/branch coverage measurement (gcov) | Low | FR-009 | Closed 2026-10-25: `make coverage`, 100% lines, 113/114 branches | TODO.md, Testing |

## Requirement Coverage

Every requirement ID maps to tests through the `test_<id>_` naming convention. The authoritative mapping lives in `docs/REQUIREMENTS_TRACEABILITY.md`.

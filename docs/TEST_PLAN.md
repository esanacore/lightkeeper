# Test Plan

This document defines how this repository is tested, what coverage it targets, and where coverage gaps currently exist.

## Test Strategy

- **Unit tests**: domain rules (parsing, thresholds, staleness) with a fixed clock and plain data. Location: `tests/test_glucose.py`, `tests/test_status.py`. Command: `python -m pytest tests/test_glucose.py tests/test_status.py`.
- **Integration tests**: the Nightscout client against an injected fetcher, the application layer against fake sources, and the CLI end to end in demo mode. Location: `tests/test_nightscout.py`, `tests/test_monitor.py`, `tests/test_cli.py`.
- **HTTP integration tests**: a fake Nightscout served on localhost exercises the real urllib fetcher, status codes, timeouts, and bad payloads. Location: `tests/test_http_integration.py`.
- **Shared vectors (parity)**: `spec/display_vectors.json` is run by `tests/test_vectors.py` and by the firmware host tests, so Python and C++ render identical screens.
- **iOS core tests**: `LightkeeperCore` runs the shared vectors with XCTest on GitHub's macOS runners (`.github/workflows/ios.yml`), so the Swift rules stay identical too. Location: `apps/ios/LightkeeperCore/Tests/`.
- **Firmware host tests**: C++17 rules built with AddressSanitizer and UBSan, run on a PC. Location: `firmware/xteink/test/host/`. Command: `make -C firmware/xteink test`.
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
| Firmware `glucose_rules` | Every shared vector + edge cases | 100% of vectors |

## Continuous Coverage Evaluation

| Date | Overall coverage | Notes |
| --- | --- | --- |
| 2026-10-17 | 100% (269 statements, 68 branches) | Baseline, 87 tests |
| 2026-10-17 | 100% Python (271 statements, 70 branches); firmware 141 checks | 117 Python tests incl. HTTP integration and 22 shared vectors; C++ host tests under sanitizers. Firmware line coverage not yet measured (GAP-006). |

## Coverage Gap Log

| Gap ID | Area / behavior | Risk | Related requirement | Status | TODO ref |
| --- | --- | --- | --- | --- | --- |
| GAP-001 | Physical e-ink panel output | Medium | FR-007 | Open | TODO.md, Testing |
| GAP-002 | Home Assistant publishing | Medium | FR-008 | Open | TODO.md, Testing |
| GAP-003 | End-to-end against a real Nightscout instance (localhost fake now covers the HTTP layer) | Medium | FR-001, FR-005 | Partially closed | TODO.md, Testing |
| GAP-004 | Long-running `--watch` soak test (memory, clock drift over days) | Medium | FR-005, FR-006 | Open | TODO.md, Testing |
| GAP-005 | Xteink device build: Wi-Fi, TLS, JSON extraction, e-paper drawing | High | FR-010 | Open | TODO.md, Testing |
| GAP-006 | Firmware line/branch coverage measurement (gcov) | Low | FR-009 | Open | TODO.md, Testing |

## Requirement Coverage

Every requirement ID maps to tests through the `test_<id>_` naming convention. The authoritative mapping lives in `docs/REQUIREMENTS_TRACEABILITY.md`.

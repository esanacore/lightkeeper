# Test Plan

This document defines how this repository is tested, what coverage it targets, and where coverage gaps currently exist.

## Test Strategy

- **Unit tests**: domain rules (parsing, thresholds, staleness) with a fixed clock and plain data. Location: `tests/test_glucose.py`, `tests/test_status.py`. Command: `python -m pytest tests/test_glucose.py tests/test_status.py`.
- **Integration tests**: the Nightscout client against an injected fetcher, the application layer against fake sources, and the CLI end to end in demo mode. Location: `tests/test_nightscout.py`, `tests/test_monitor.py`, `tests/test_cli.py`.
- **End-to-end tests**: against a real self-hosted Nightscout test instance with simulated uploads, planned once Nightscout is stood up (see GAP-003).
- **Manual validation**: before Kaitlin relies on any display, run it side by side with the primary app for at least one full sensor session and log any mismatch, freeze, or missed STALE.

## How to Run Tests

- Full suite: `python -m pytest --cov`
- With coverage: `python -m pytest --cov --cov-report=term-missing`
- A single test or subset: `python -m pytest -k fr003`

## Coverage Targets

| Scope | Metric | Floor |
| --- | --- | --- |
| Repository default | Line + branch | 90% |
| Domain layer (safety rules) | Line + branch | 100% |
| Nightscout client (credentials, untrusted input) | Line + branch | 95% |

## Continuous Coverage Evaluation

| Date | Overall coverage | Notes |
| --- | --- | --- |
| 2026-10-17 | 100% (269 statements, 68 branches) | Baseline, 87 tests |

## Coverage Gap Log

| Gap ID | Area / behavior | Risk | Related requirement | Status | TODO ref |
| --- | --- | --- | --- | --- | --- |
| GAP-001 | Physical e-ink panel output | Medium | FR-007 | Open | TODO.md, Testing |
| GAP-002 | Home Assistant publishing | Medium | FR-008 | Open | TODO.md, Testing |
| GAP-003 | End-to-end against a real Nightscout instance | Medium | FR-001, FR-005 | Open | TODO.md, Testing |
| GAP-004 | Long-running `--watch` soak test (memory, clock drift over days) | Medium | FR-005, FR-006 | Open | TODO.md, Testing |

## Requirement Coverage

Every requirement ID maps to tests through the `test_<id>_` naming convention. The authoritative mapping lives in `docs/REQUIREMENTS_TRACEABILITY.md`.

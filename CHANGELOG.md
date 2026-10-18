# Changelog

All notable user-facing changes to this project are documented in this file.

This project follows semantic versioning.

## Unreleased

### Added

- `lightkeeper` read-only Nightscout display: strict entry parsing, configurable thresholds, staleness and future-timestamp protection, short ASCII rendering for e-ink, safe degradation when Nightscout fails, and a CLI with `--demo` and `--watch`.
- `--svg PATH` writes each screen as an SVG image of the e-paper panel (FR-011).
- Display-state gallery (`docs/DISPLAY_STATES.md`) and the demo page's state table, both generated from the shared vectors, with tests that fail if either drifts.
- Shared golden display vectors (`spec/display_vectors.json`) run by both Python and firmware tests.
- `firmware/xteink`: safety rules ported to C++17 for the Xteink X4/X3 (ESP32-C3), with host tests under sanitizers (ADR-0006) and a clang-format check (ADR-0007, proposed).
- HTTP integration tests against a fake Nightscout on localhost.
- Static analysis: ruff (lint, format, bandit rules), strict mypy, clang-format, all in the declared suite and pre-commit.
- `tools/doctor.py` prerequisite check, `.python-version`, and a devcontainer with Python, the C++ toolchain, and the dev tools.
- `.env.example` listing every setting, checked against `docs/ENV_VARS.md` in CI.
- Docs: safety boundary and hazard log, security model (data classification, retention, STRIDE threat model), ADRs 0001 to 0007 with an index, product requirements, traceability matrix, test plan, OTS inventory, phased backlog, and a real wiki.
- Offline `demo.html` showing every display state.
- `docs/ROADMAP.md` and ADR-0008 (proposed): a companion iOS app, read-only first, with bolus requests only through Trio's remote protocol.
- `spec_version` field in `spec/display_vectors.json`.

### Changed

- Project renamed to Lightkeeper: Python package and command `lightkeeper`, threshold variables now `LK_*`, firmware namespace `lk`.
- Docs updated for Omnipod 5 support shipping in Trio v1.0.0 (no longer beta).
- CI: Python set up and declared suite run in strict mode; env-contract check now actually runs; wiki workflow write access limited to its publish job; Dependabot watches pip.

### Fixed

- STALE while Nightscout is unreachable now renders four lines instead of five, so it fits the e-ink limit (found by the shared vectors).

### Security

- Nightscout client is HTTPS-only, read-only, and redacts the access token from all errors.
- Private vulnerability reporting documented in `.github/SECURITY.md`.

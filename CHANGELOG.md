# Changelog

All notable user-facing changes to this project are documented in this file.

This project follows semantic versioning.

## Unreleased

### Added

- `glucose_watch` read-only Nightscout display: strict entry parsing, configurable thresholds, staleness and future-timestamp protection, short ASCII rendering for e-ink, safe degradation when Nightscout fails, and a CLI with `--demo` and `--watch`.
- Safety boundary and hazard log (`docs/SAFETY.md`).
- ADRs 0002 to 0005: Trio on iPhone as dosing controller, self-hosted Nightscout, no insulin delivery code in this repo, Python display layer.
- Product requirements, traceability matrix, test plan, OTS inventory, and phased rollout backlog.
- Offline `demo.html` showing every display state.
- Shared golden display vectors (`spec/display_vectors.json`) run by both Python and firmware tests.
- `firmware/xteink`: safety rules ported to C++17 for the Xteink X4/X3 (ESP32-C3), with host tests under sanitizers (ADR-0006).
- HTTP integration tests against a fake Nightscout on localhost.
- CI installs Python and runs the declared suite in strict mode.

### Changed

### Fixed

- STALE while Nightscout is unreachable now renders four lines instead of five, so it fits the e-ink limit (found by the shared vectors).

### Removed

### Security

- Nightscout client is HTTPS-only, read-only, and redacts the access token from all errors.

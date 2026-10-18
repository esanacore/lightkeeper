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

### Changed

### Fixed

### Removed

### Security

- Nightscout client is HTTPS-only, read-only, and redacts the access token from all errors.

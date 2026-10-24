# Changelog

All notable user-facing changes to this project are documented in this file.

This project follows semantic versioning.

## Unreleased

### Changed

- README: a version line under the badge, and the How It Fits Together diagram as a top-down image rendered from `assets/diagrams/`, so it also shows in GitHub's mobile apps.

### Fixed

- `tools/doctor.py` no longer hangs on Windows when run under pytest: the WSL probe closes stdin and allows for a cold WSL start.

## [0.1.0] - 2026-10-24

First tagged release (Phase 0, the foundation).

### Fixed

- A single malformed Nightscout entry (`NaN`, `Infinity`, an absurd timestamp) no longer discards the good readings around it or reports "Nightscout unreachable"; timestamps are bounded to 2000-2100 so a seconds-instead-of-milliseconds upload is rejected instead of reading as 1970 (HAZ-011, all three implementations).
- `--watch` survives a failed `--svg` write (full disk, locked file) and logs it instead of exiting; Ctrl+C exits cleanly; output is flushed each cycle so `journalctl -f` is live under systemd. Run-once returns exit code 2 on a failed write.
- The SVG written by `--svg` carries a small `written HH:MM UTC` stamp so a dashboard can tell a live writer from a dead one.
- Readings that share a timestamp (several uploaders) resolve to the lower value in every implementation, independent of upload order.
- iOS: numbers too large for `Int` now throw instead of crashing the app; settings edits land in a draft, Save is disabled with the reason while thresholds are invalid, and an invalid set on disk resets to defaults; the app re-ages the last reading the instant it returns to the foreground and shrinks and strikes through a STALE number (HAZ-012).
- Firmware: NaN values are rejected before any cast (previously undefined behaviour that happened to pass).

### Added

- `docs/SAFETY.md`: Intended Use and Classification section (IEC 62304 Class A-equivalent rationale, limitations list), HAZ-011 and HAZ-012.
- Shared vector `huge_value_rejected`; every implementation now asserts the vector `spec_version` it was written for.
- Reserved requirements FR-013 (mmol/L), FR-014 (delta), FR-015 (device status) in the PRD's Planned section.
- Shared vector schema: an age can be given in `seconds_ago`, a case can hold several `entries` (each with its own age), and a case can carry custom `thresholds`. Sixteen new cases pin the 15-minutes-plus-one-second and 2-minute future-skew boundaries to the second, same-timestamp ties, poisoned entries next to good ones, a rejected newest entry that must not make an older one look fresh, and custom thresholds, in Python, firmware, and Swift alike. Existing cases are unchanged, so `spec_version` stays 1.
- `LightkeeperCore` (Swift) builds and passes its tests on Linux and Windows as well as Apple platforms, and CI runs it on Linux; a JSON boolean is still rejected as a glucose value on every platform.
- `tools/doctor.py` on Windows looks for `make` and `g++` inside WSL, where the firmware host tests can link the sanitizers.
- Firmware: `newest_reading` picks the newest trustworthy entry from a fetch, with the same lower-value tie-break as Python and Swift.

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
- Project hygiene: `CODE_OF_CONDUCT.md`, `SUPPORT.md`, `CITATION.cff`, issue templates with a safety triage question, safety line in the PR template.
- iOS companion app, read-only layer: `LightkeeperCore` Swift package (rules + Nightscout client) tested against the shared vectors, SwiftUI app with Keychain-held token, built in CI on macOS runners (FR-012, ADR-0008 Phase 5a).
- Brand kit: lighthouse mark (light, dark, mono), app icon, palette, social preview, and `docs/BRAND.md`.
- `docs/HARDWARE.md`: buyer's guide for the bedside Pi display, the Xteink X4 Pro, and an ESP32-S3 bench board.
- `docs/COMMUNITY_RESEARCH.md`: what the community says about display and alert tools, with twelve implications for Lightkeeper.

### Changed

- Project renamed to Lightkeeper: Python package and command `lightkeeper`, threshold variables now `LK_*`, firmware namespace `lk`.
- Docs updated for Omnipod 5 support shipping in Trio v1.0.0 (no longer beta).
- CI: Python set up and declared suite run in strict mode; env-contract check now actually runs; wiki workflow write access limited to its publish job; Dependabot watches pip.

### Fixed

- Firmware: `age_minutes` now floors milliseconds exactly like Python for negative ages; `classify` returns NO DATA when thresholds are invalid instead of judging a number against bad limits.

- STALE while Nightscout is unreachable now renders four lines instead of five, so it fits the e-ink limit (found by the shared vectors).

### Security

- Nightscout client is HTTPS-only, read-only, and redacts the access token from all errors.
- Private vulnerability reporting documented in `.github/SECURITY.md`.

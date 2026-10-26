# Changelog

All notable user-facing changes to this project are documented in this file.

This project follows semantic versioning.

## Unreleased

### Added

- Home Assistant over MQTT discovery (FR-008, ADR-0010 accepted, HAZ-013). Set `LK_MQTT_HOST` (and the other `LK_MQTT_*` settings) to publish Glucose level, Glucose, and Glucose reading age sensors. A Last Will and `expire_after` make them unavailable if the publisher stops, state is never retained, the number is blank whenever the level is STALE or NO DATA, TLS is the default, and a broker failure never stops the display. The MQTT client is a small publish-only implementation in the standard library.
- `--json PATH` writes the current status (level, number, trend, age, lines, error) atomically, for dashboards.
- `lightkeeper.infrastructure.epaper_bitmap`: draws the display lines as a 1-bit 296x128 bitmap with the project's own 5x8 font (standard library only), as a PNG preview or a packed buffer in Waveshare's 2.9" panel layout. This is the Raspberry Pi display groundwork (FR-007); the panel driver follows when the hardware arrives.
- iOS app unit tests (`apps/ios/Lightkeeper/Tests/`), run on a simulator in CI: an impossible threshold set on disk resets to the defaults and is saved back, and returning to the foreground turns an old reading STALE without waiting for a fetch.

### Changed

- Firmware: `make -C firmware/xteink coverage` measures line and branch coverage with gcov (100% of lines, 113 of 114 branches); new host tests cover the remaining threshold, enum-fallback, inconsistent-status, and tie-break branches.
- The readable Nightscout token is now sent in the `api-secret` request header instead of `?token=` in the URL, by the Python tool and the iOS app, so it no longer appears in proxy or hosting access logs (ADR-0009, accepted). ADR-0009 weighed this against JWT bearer auth and the v3 API, using the Nightscout v15.0.9 source. Custom fetchers passed to `NightscoutClient` now take `(url, headers, timeout)`.
- README: a version line under the badge, and the How It Fits Together diagram as a top-down image rendered from `assets/diagrams/`, so it also shows in GitHub's mobile apps.
- `docs/SETUP.md` compares Nightscout hosts (managed and VPS) with a recommendation; `docs/HARDWARE.md` carries prices and stock checked on 2026-10-25, and the bedside display is now the Waveshare 2.9" Touch e-Paper HAT because the plain HAT is discontinued.
- `docs/SAFETY_REVIEW.md`: a one-page sign-off sheet for the person with diabetes to confirm or change the thresholds and stale limit.
- ADR-0007 (firmware C++ style: Google base, Python-mirroring names, 100 columns) is Accepted.
- The demo page is published at https://esanacore.github.io/lightkeeper/ by a new `pages.yml` workflow, and the README links it. Its links to repository docs are now absolute, so they work from the published page.

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
- `firmware/xteink`: safety rules ported to C++17 for the Xteink X4/X3 (ESP32-C3), with host tests under sanitizers (ADR-0006) and a clang-format check (ADR-0007).
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

# Agent Handoff

This document helps transition work between AI agent sessions or between agents.

**Before starting your session**, check `docs/SESSION_PLAN.md` for planned work and `docs/MEMORY.md` for durable learnings. Read `docs/SAFETY.md` before touching anything in `src/`.

Replace the entry below at the end of every push; only the latest handoff is kept. `constitution/scripts/check_next_steps.sh` checks the procedure's format.

## Latest Handoff

### Session: 2026-10-23 to 2026-10-25 (vectors, portability, release, decisions, then groundwork)
- **Latest work (2026-10-25)**: GAP-006 closed (`make -C firmware/xteink coverage`: 100% of lines, 113 of 114 branches). FR-007 groundwork: `epaper_bitmap.py` rasterizes the display lines to a 296x128 1-bit bitmap with the project's own 5x8 font, as a PNG or a Waveshare panel buffer (on-panel orientation unchecked, GAP-001). ADR-0010 proposes MQTT discovery for Home Assistant (step 14). GAP-004 partly closed by an accelerated three-day soak (`tests/test_soak.py`). PyPI: `lightkeeper` and `lightkeeper-display` are both free. Earlier the same session: ADR-0009 accepted and implemented (token in the `api-secret` header), iOS app tests, v0.1.0 released, live demo on Pages, ADR-0007 accepted, safety review sheet, Nightscout host comparison, hardware prices checked. Verification: 235 Python tests at 100% line and branch, 294 firmware checks under ASan/UBSan, Swift package 13 of 13 locally, every CI workflow green on the last pushed commit.
- **Accomplishments**: Extended `spec/display_vectors.json` with three optional, additive forms: `seconds_ago` as an alternative to `minutes_ago`, an `entries` list (each item an `entry` plus its own age) as an alternative to `entry`, and a `thresholds` object (all five fields). Added 16 cases (39 total): staleness and future-skew boundaries to the second, same-timestamp tie, newest-wins in any order, poisoned entries next to a good one, a rejected newest entry that must not freshen an older one, all entries rejected, and seven custom-threshold cases. Existing cases are unchanged, so `spec_version` stays 1. All three runners now go through the multi-entry path (Python `parse_entries`, Swift `parseEntries`, new firmware `lk::newest_reading` with the lower-value tie-break). Gallery, demo labels, wiki (counts and the Display States mirror), TEST_PLAN, PRD acceptance text, TODO, and CHANGELOG updated. Existing per-implementation unit tests were kept on purpose: they check more than the vectors (full sort order, NaN, which JSON cannot carry) and back FR-001 and FR-002 traceability.
- **Verification Run**: ruff, ruff format, strict mypy, pytest 174 of 175 at 100% line and branch coverage (`test_doctor_passes_on_a_ready_machine` fails locally only because `make` is not on the Windows PATH); firmware host tests in WSL Ubuntu under ASan/UBSan, 287 checks and 0 failures over 39 vectors; clang-format clean; a mutation flipping the firmware tie-break fails `same_timestamp_lower_value_wins` as intended. Swift: the vector tests pass in a scratch copy of the package on the Windows Swift 6.4 toolchain, with `NightscoutClient.swift` left out and the Apple-only `kCFBoolean` check removed; the real package is confirmed only by the macOS `iOS` workflow. Constitution checkers: compliance, architecture, traceability, OTS, env vars, secrets, demo page, README, version alignment, wiki links, and next-steps all pass; the diff-based freshness checks run in CI.
- **Follow-up in the same session**: The vector commit `9441965` went green in every workflow, iOS included. Then `LightkeeperCore` was made to build without Apple-only APIs (`FoundationNetworking` guarded, the `kCFBoolean` identity check limited to Darwin), and it now passes all 8 tests with the Windows Swift 6.4 toolchain. A new `core-tests-linux` job in `ios.yml` (`swift:6.1-noble`, OTS-113) keeps it that way, and `testJSONBooleansAreNotNumbers` covers the JSONSerialization path on every platform. `tools/doctor.py` now looks inside WSL for `make` and `g++` on Windows, because MinGW cannot link the sanitizers (confirmed on this machine). Docs that recommended MSYS2 or Git Bash for the firmware tests now say WSL. Python: 177 of 177 at 100% coverage.
- **Repository**: github.com/esanacore/lightkeeper (public).
- **Known Blockers**: Release tag, GitHub Pages, and README layout changes wait on Eric. No Nightscout instance yet (GAP-003). No Xteink hardware yet (GAP-005).
- **Context Hints**: Vector schema: one of `entry` or `entries`; each entry has exactly one of `minutes_ago` or `seconds_ago`; `thresholds` is all five keys or absent (`tests/test_vectors.py` enforces this). Firmware vectors are generated as one `VectorEntry` array per case plus `kVectors`, and `vectors.inc` is included at namespace scope. On this Windows machine, run the firmware tests with `wsl -d Ubuntu -- make -C firmware/xteink test`, and initialize the `constitution` submodule before running the checkers. README structure is locked (`docs/MEMORY.md`). Use Conventional Commits.

#### Next Steps

**Human action required:** steps 1 (done), 2 (done), 3 (done), 4 (done), 5 (done), 6, 7, 8, 13 (done), 14 (done), and 15.

1. [x] **HUMAN** — Approve cutting release v0.1.0 (approved 2026-10-24; tagged and published)
   - **Why a human:** a tag and GitHub Release are public, permanent publications.
   - **Done when:** Eric says go; then an agent moves Unreleased to `## [0.1.0] - <date>`, tags `v0.1.0`, and publishes the GitHub Release, and `check_release_tag_alignment.sh` passes.
2. [x] **HUMAN** — Decide on README presentation changes the constitution asks for (approved 2026-10-24: version line and top-down rendered diagram added; the demo link lands with step 3)
   - **Why a human:** the README layout is locked by Eric's house-style rule.
   - **Done when:** Eric has approved or declined a version line, a top-to-bottom (TD) diagram with a committed rendered image, and a published demo link.
3. [x] **HUMAN** — Turn on GitHub Pages (Settings, Pages, Source: GitHub Actions) if the demo should be published (approved 2026-10-24; enabled via the API, `pages.yml` deploys it, README links it)
   - **Why a human:** repository settings change.
   - **Done when:** Pages is enabled; an agent then adds the deploy workflow and links the URL.
4. [x] **HUMAN** — Approve or reject ADR-0007 (C++ naming mirrors Python, 100 columns) (accepted as written 2026-10-24)
   - **Why a human:** style deviations from the constitution need the owner's approval.
   - **Done when:** ADR-0007 is Accepted or replaced, and the decision is recorded in `docs/MEMORY.md`.
5. [x] **HUMAN** — Confirm the Apache-2.0 license and decide on the gstack section in `CLAUDE.md` (2026-10-24: Apache-2.0 kept, gstack section kept)
   - **Why a human:** licensing and tooling choices are the owner's.
   - **Done when:** `LICENSE` is confirmed and the gstack section is kept (with gstack installed) or deleted.
6. [ ] **HUMAN** — Kaitlin reviews `docs/SAFETY.md` and the default thresholds
   - **Why a human:** thresholds and the safety boundary are her call, with her care team.
   - **Done when:** Kaitlin has filled in and signed `docs/SAFETY_REVIEW.md` (written 2026-10-24), and the thresholds in `docs/ENV_VARS.md` are confirmed or changed to match.
7. [ ] **HUMAN** — Choose Nightscout hosting and deploy it (Phase 1)
   - **Why a human:** needs accounts, a domain, and a secret only Eric should hold.
   - **Done when:** a host is chosen from the comparison in `docs/SETUP.md` ("Choosing a host", 2026-10-25), recorded in an ADR, Nightscout is reachable over HTTPS, and a readable-role token exists.
8. [ ] **HUMAN** — Buy the Tier 1 hardware in `docs/HARDWARE.md` (Pi Zero 2 WH + 2.9" Touch e-Paper HAT, Xteink X4 Pro, ESP32-S3 bench board)
   - **Why a human:** hardware purchase, and flashing risks bricking a device.
   - **Done when:** the parts are on the bench (prices and stock checked 2026-10-25 in `docs/HARDWARE.md`: the bare Pi Zero 2 WH was sold out and the display is now the 2.9" Touch e-Paper HAT); CrossPoint has been flashed and stock firmware restored once on the Xteink.
9. [ ] **AUTOMATED** — CI runs the constitution workflows on every push to main, `iOS` (macOS and Linux package tests, simulator build) when iOS code or the vectors change, and `Demo page` (Pages deploy) when `demo.html` changes; watch for a red run.
10. [x] **AGENT** — Propose the env-workflow path fix upstream: [esanacore/engineering-constitution#97](https://github.com/esanacore/engineering-constitution/pull/97), merged by Eric 2026-10-26 (`1470868`).
16. [ ] **AUTOMATED** — When the next constitution release is cut, `bump_adopters.sh` opens a PR here re-pinning `constitution/` to a commit that includes #97; until then the submodule stays at `db43ae7` and this repo's own `constitution-env.yml` already carries the fix.
11. [x] **AGENT** — iOS: unit tests for `Settings.load()` resetting an invalid set and `reclassify()` going STALE without a fetch: `LightkeeperTests` target (`SettingsTests`, `GlucoseModelTests`), 9 of 9 passing on a simulator in `ios.yml`; merged from [esanacore/lightkeeper#2](https://github.com/esanacore/lightkeeper/pull/2).
12. [x] **AGENT** — Write an ADR evaluating Nightscout v3 JWT bearer auth with `AUTH_DEFAULT_ROLES=denied`: ADR-0009 (Proposed) recommends the `api-secret` header on v1 instead, with JWT as the fallback.
13. [x] **HUMAN** — Accept or reject ADR-0009 (accepted 2026-10-25; Python and Swift clients now send the token in the `api-secret` header)
   - **Why a human:** a change to how credentials travel needs the owner's approval.
   - **Done when:** ADR-0009 is Accepted or Rejected; if accepted, an agent changes the clients in one commit (done) and runs the real-instance check once Nightscout exists (step 7; tracked in `TODO.md`).
14. [x] **HUMAN** — Pick the Home Assistant transport in ADR-0010 (MQTT discovery accepted 2026-10-26; HAZ-013 written; implemented with fake-broker tests)
   - **Why a human:** it adds a new output that Home Assistant automations can alert on, and a broker credential; the owner decides.
   - **Done when:** ADR-0010 is Accepted (or replaced), and `docs/SAFETY.md` has a hazard entry for the Home Assistant path; an agent then implements it with fake-broker tests (GAP-002).
15. [ ] **HUMAN** — Set up the Mosquitto add-on and a broker user in Home Assistant, then point a display at it (`docs/SETUP.md`, Home Assistant)
   - **Why a human:** it needs the household's Home Assistant, a broker account and password, and a decision about which automations to add.
   - **Done when:** the three Lightkeeper sensors appear in Home Assistant, the example automations are added if wanted, and stopping the publisher shows `unavailable`; an agent records the result in `docs/TEST_PLAN.md` (closes GAP-002).

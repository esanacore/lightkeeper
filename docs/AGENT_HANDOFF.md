# Agent Handoff

This document helps transition work between AI agent sessions or between agents.

**Before starting your session**, check `docs/SESSION_PLAN.md` for planned work and `docs/MEMORY.md` for durable learnings. Read `docs/SAFETY.md` before touching anything in `src/`.

Replace the entry below at the end of every push; only the latest handoff is kept. `constitution/scripts/check_next_steps.sh` checks the procedure's format.

## Latest Handoff

### Session: 2026-10-18 (reviews applied, wiki, iOS hardening)
- **Accomplishments**: Applied an adversarial safety review and a docs/product review. Python: one malformed entry (`NaN`, `Infinity`, absurd timestamp) no longer blanks the display or reports "Nightscout unreachable"; timestamps bounded to 2000-2100; `--watch` survives failed SVG writes, exits cleanly on Ctrl+C, flushes output per cycle; SVG carries a `written HH:MM UTC` stamp; same-timestamp duplicates resolve to the lower value (HAZ-011). Firmware: NaN rejected before any cast, date bounds, `spec_version` asserted. iOS: huge numbers throw instead of trapping, settings edit a draft with Save disabled while invalid, invalid set on disk resets to defaults, foreground re-classification, STALE number struck through (HAZ-012). `docs/SAFETY.md` gained Intended Use and Classification (Class A-equivalent rationale, limitations), HAZ-011, HAZ-012. Demo page restyled to the brand palette with a button for every vector and an in-panel SIMULATED label. Reserved FR-013 (mmol/L), FR-014 (delta), FR-015 (device status). Normative docs now say "the person with diabetes" and "the care team" instead of a name (README unchanged, structure locked). Wiki expanded to 20 pages with `tests/test_wiki.py` guarding links and freshness. Added CODE_OF_CONDUCT, SUPPORT, CITATION.cff, issue templates.
- **Verification Run**: ruff, ruff format, strict mypy, pytest at 100% line and branch coverage, clang-format, firmware host checks under ASan/UBSan (23 shared vectors), all constitution checkers except release-tag alignment (needs the v0.1.0 tag). Swift tests run on the macOS CI runner (no Swift toolchain here); confirm the `iOS` workflow is green after this push.
- **Repository**: github.com/esanacore/lightkeeper (public).
- **Known Blockers**: Release tag, GitHub Pages, and README layout changes wait on Eric. No Nightscout instance yet (GAP-003). No Xteink hardware yet (GAP-005). Swift changes in this session were compiled only by CI.
- **Context Hints**: README structure is locked (`docs/MEMORY.md`). Rule changes must update `spec/display_vectors.json`, Python, firmware, and Swift together, then run `python tools/gen_display_gallery.py`; bump `spec_version` (and its three assertions) only when an existing vector changes. New demo buttons are the label map in `demo.html`; `tests/test_gallery.py` requires a label for every vector. Use Conventional Commits.

#### Next Steps

**Human action required:** steps 1, 2, 3, 4, 5, 6, 7, and 8.

1. [ ] **HUMAN** — Approve cutting release v0.1.0
   - **Why a human:** a tag and GitHub Release are public, permanent publications.
   - **Done when:** Eric says go; then an agent moves Unreleased to `## [0.1.0] - <date>`, tags `v0.1.0`, and publishes the GitHub Release, and `check_release_tag_alignment.sh` passes.
2. [ ] **HUMAN** — Decide on README presentation changes the constitution asks for
   - **Why a human:** the README layout is locked by Eric's house-style rule.
   - **Done when:** Eric has approved or declined a version line, a top-to-bottom (TD) diagram with a committed rendered image, and a published demo link.
3. [ ] **HUMAN** — Turn on GitHub Pages (Settings, Pages, Source: GitHub Actions) if the demo should be published
   - **Why a human:** repository settings change.
   - **Done when:** Pages is enabled; an agent then adds the deploy workflow and links the URL.
4. [ ] **HUMAN** — Approve or reject ADR-0007 (C++ naming mirrors Python, 100 columns)
   - **Why a human:** style deviations from the constitution need the owner's approval.
   - **Done when:** ADR-0007 is Accepted or replaced, and the decision is recorded in `docs/MEMORY.md`.
5. [ ] **HUMAN** — Confirm the Apache-2.0 license and decide on the gstack section in `CLAUDE.md`
   - **Why a human:** licensing and tooling choices are the owner's.
   - **Done when:** `LICENSE` is confirmed and the gstack section is kept (with gstack installed) or deleted.
6. [ ] **HUMAN** — Kaitlin reviews `docs/SAFETY.md` and the default thresholds
   - **Why a human:** thresholds and the safety boundary are her call, with her care team.
   - **Done when:** thresholds in `docs/ENV_VARS.md` are confirmed or changed.
7. [ ] **HUMAN** — Choose Nightscout hosting and deploy it (Phase 1)
   - **Why a human:** needs accounts, a domain, and a secret only Eric should hold.
   - **Done when:** Nightscout is reachable over HTTPS and a readable-role token exists.
8. [ ] **HUMAN** — Buy the Tier 1 hardware in `docs/HARDWARE.md` (Pi Zero 2 WH + 2.9" e-paper HAT, Xteink X4 Pro, ESP32-S3 bench board)
   - **Why a human:** hardware purchase, and flashing risks bricking a device.
   - **Done when:** the parts are on the bench; CrossPoint has been flashed and stock firmware restored once on the Xteink.
9. [ ] **AUTOMATED** — CI runs all constitution workflows and the `iOS` workflow (Swift tests on macOS) on the pushed commit; watch for a red run.
10. [ ] **AGENT** _(suggestion)_ — Propose the env-workflow path fix upstream in the engineering-constitution repo.
11. [ ] **AGENT** _(suggestion)_ — Extend the vector schema (`seconds_ago`, multiple entries, custom thresholds) so the duplicate-timestamp and 15-minutes-plus-one-second cases become shared vectors rather than per-implementation unit tests.

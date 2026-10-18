# Agent Handoff

This document helps transition work between AI agent sessions or between agents.

**Before starting your session**, check `docs/SESSION_PLAN.md` for planned work and `docs/MEMORY.md` for durable learnings. Read `docs/SAFETY.md` before touching anything in `src/`.

Replace the entry below at the end of every push; only the latest handoff is kept. `constitution/scripts/check_next_steps.sh` checks the procedure's format.

## Latest Handoff

### Session: 2026-10-18 (compliance push)
- **Accomplishments**: Constitution compliance pass and visuals. Added the SVG panel renderer and `--svg` option, a generated display-state gallery, and a demo whose states come from the shared vectors (FR-011). Added ruff, strict mypy, and clang-format to the declared suite and pre-commit. Fixed the env-contract workflow (it never ran), scoped wiki write permissions, added Dependabot pip, CODEOWNERS, a filled-in `.github/SECURITY.md`, `docs/SECURITY_MODEL.md` (classification, retention, STRIDE), an ADR index with gatekeepers, ADR-0007 (proposed C++ style), a real wiki, `.env.example`, `.python-version`, `tools/doctor.py`, and a devcontainer. Updated docs for Omnipod 5 shipping in Trio v1.0.0. Removed `.constitution-bootstrap/`.
- **Verification Run**: Declared full suite (`--strict`): ruff, ruff format, mypy (strict), 133 pytest tests at 100% line and branch coverage, clang-format check, and 141 firmware checks under ASan/UBSan, all passing. Every constitution checker passes except release-tag alignment, which needs the v0.1.0 tag (step 1).
- **Repository**: github.com/esanacore/lightkeeper (public).
- **Known Blockers**: Release tag, GitHub Pages, and README layout changes wait on Eric. No Nightscout instance yet (GAP-003). No Xteink hardware yet (GAP-005).
- **Context Hints**: README structure is locked (`docs/MEMORY.md`). Rule changes must update `spec/display_vectors.json`, Python, and firmware together, then run `python tools/gen_display_gallery.py`. Use Conventional Commits.

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
9. [ ] **AUTOMATED** — CI runs all constitution workflows on the pushed commit; watch for a red run.
10. [ ] **AGENT** _(suggestion)_ — Propose the env-workflow path fix upstream in the engineering-constitution repo.

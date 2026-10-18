# Agent Handoff

This document helps transition work between AI agent sessions or between agents.

**Before starting your session**, check `docs/SESSION_PLAN.md` for planned work and `docs/MEMORY.md` for durable learnings. Read `docs/SAFETY.md` before touching anything in `src/`.

Replace the entry below at the end of every push; only the latest handoff is kept. `constitution/scripts/check_next_steps.sh` checks the procedure's format.

## Latest Handoff

### Session: 2026-10-17
- **Accomplishments**: Bootstrapped the repo with the engineering constitution. Wrote the safety boundary and hazard log, ADRs 0001 to 0005, requirements, traceability, test plan, OTS inventory, setup, operations, and the phased backlog. Built `glucose_watch` 0.1.0 (read-only Nightscout display) with 87 tests.
- **Verification Run**: `python -m pytest --cov`: 87 passed, 100% line and branch coverage. `check_compliance.sh --product .` clean.
- **Known Blockers**: No Nightscout instance yet, so GAP-003 (end-to-end tests) is open. No remote repository yet.
- **Context Hints**: `docs/SAFETY.md` and `docs/adr/0004-no-insulin-delivery-code-in-this-repo.md` define what this repo must never do. Phases are in `docs/MVP_BACKLOG.md`.

#### Next Steps

**Human action required:** steps 1, 2, 3, 4, and 6.

1. [ ] **HUMAN** — Create the GitHub repository and push
   - **Why a human:** needs Eric's GitHub account and the choice of public or private.
   - **Done when:** `git push -u origin main` succeeds and the constitution CI workflows run.
2. [ ] **HUMAN** — Confirm the license
   - **Why a human:** Apache-2.0 was chosen as a default; licensing is the owner's decision.
   - **Done when:** `LICENSE` and `pyproject.toml` match the chosen license.
3. [ ] **HUMAN** — Kaitlin reviews `docs/SAFETY.md` and the default thresholds
   - **Why a human:** thresholds and the safety boundary are her call, with her care team.
   - **Done when:** thresholds in `docs/ENV_VARS.md` are confirmed or changed, and the acceptance checkbox in `docs/PRODUCT_REQUIREMENTS.md` is ticked.
4. [ ] **HUMAN** — Choose Nightscout hosting and deploy it (Phase 1)
   - **Why a human:** needs accounts, a domain, and a secret only Eric should hold.
   - **Done when:** Nightscout is reachable over HTTPS and a readable-role token exists.
5. [ ] **AGENT** — Add a Python setup step to the constitution test workflow and switch it to `--strict`.
6. [ ] **HUMAN** — Talk with Kaitlin's endocrinologist about Trio before Phase 2
   - **Why a human:** a clinical conversation.
   - **Done when:** there is a plan for settings review and an open-loop start date.
7. [ ] **AGENT** _(suggestion)_ — Start the Raspberry Pi e-paper adapter (FR-007) once hardware is chosen.

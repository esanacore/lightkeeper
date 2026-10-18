# Agent Handoff

This document helps transition work between AI agent sessions or between agents.

**Before starting your session**, check `docs/SESSION_PLAN.md` for planned work and `docs/MEMORY.md` for durable learnings. Read `docs/SAFETY.md` before touching anything in `src/`.

Replace the entry below at the end of every push; only the latest handoff is kept. `constitution/scripts/check_next_steps.sh` checks the procedure's format.

## Latest Handoff

### Session: 2026-10-17 (second push)
- **Accomplishments**: CI now installs Python and runs the declared suite with `--strict`. Added HTTP integration tests against a fake Nightscout on localhost. Added shared golden vectors (`spec/display_vectors.json`) and ported the safety rules to C++17 for the Xteink X4/X3 (`firmware/xteink`, ADR-0006). The vectors caught a real divergence: STALE plus unreachable rendered five lines in Python; both implementations now render four.
- **Verification Run**: `python -m pytest --cov`: 117 passed, 100% line and branch. `make -C firmware/xteink test`: 141 checks, 0 failures under ASan/UBSan. Mutation check: loosening the staleness rule in C++ made 4 checks fail. Constitution compliance, traceability, next-steps, README, architecture, and secrets checks pass.
- **Repository**: github.com/esanacore/lightkeeper (public), all constitution CI workflows green.
- **Known Blockers**: No Nightscout instance yet (GAP-003). No Xteink hardware yet (GAP-005).
- **Context Hints**: Any rule change must update `spec/display_vectors.json`, the Python code, and `firmware/xteink/lib/glucose_rules` in the same commit. Read `docs/SAFETY.md` and ADR-0004 before touching `src/` or `firmware/`.

#### Next Steps

**Human action required:** steps 1, 2, 3, 4, and 6.

1. [ ] **HUMAN** — Confirm the license
   - **Why a human:** Apache-2.0 was chosen as a default; licensing is the owner's decision.
   - **Done when:** `LICENSE` and `pyproject.toml` match the chosen license.
2. [ ] **HUMAN** — Kaitlin reviews `docs/SAFETY.md` and the default thresholds
   - **Why a human:** thresholds and the safety boundary are her call, with her care team.
   - **Done when:** thresholds in `docs/ENV_VARS.md` are confirmed or changed, and the acceptance checkbox in `docs/PRODUCT_REQUIREMENTS.md` is ticked.
3. [ ] **HUMAN** — Choose Nightscout hosting and deploy it (Phase 1)
   - **Why a human:** needs accounts, a domain, and a secret only Eric should hold.
   - **Done when:** Nightscout is reachable over HTTPS and a readable-role token exists.
4. [ ] **HUMAN** — Buy an Xteink X4 (or X3) and confirm it can be flashed
   - **Why a human:** hardware purchase, and flashing risks bricking the device.
   - **Done when:** the device is on the bench and a community firmware has been flashed and restored once.
5. [ ] **AGENT** — Add the PlatformIO ESP32-C3 device project for the Xteink (Wi-Fi, HTTPS, JSON field extraction, e-paper drawing, deep sleep) on top of `glucose_rules`.
6. [ ] **HUMAN** — Talk with Kaitlin's endocrinologist about Trio, and about Dexcom G7 versus Libre 3 Plus, before Phase 2
   - **Why a human:** a clinical conversation.
   - **Done when:** there is a plan for settings review, a CGM decision, and an open-loop start date.
7. [ ] **AGENT** _(suggestion)_ — Measure firmware coverage with gcov (GAP-006).

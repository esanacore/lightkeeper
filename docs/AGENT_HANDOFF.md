# Agent Handoff

This document helps transition work between AI agent sessions or between agents.

**Before starting your session**, check `docs/SESSION_PLAN.md` for planned work and `docs/MEMORY.md` for durable learnings. Read `docs/SAFETY.md` before touching anything in `src/`.

Replace the entry below at the end of every push; only the latest handoff is kept. `constitution/scripts/check_next_steps.sh` checks the procedure's format.

## Latest Handoff

### Session: 2026-10-27 to 2026-10-28 (Keeper's Logbook batch: UX and more platforms)
- **Goal**: Eric asked to sharpen what exists, build out more platforms, and bring the UI up to what industry leaders do, with a home-grown, lo-fi look that suits an open-source project. The result is "Keeper's Logbook, 1-bit edition", built in three waves of items (LK-01 to LK-11). Each item was built in its own worktree, reviewed by two adversarial lenses, fixed, then merged into `ux/keepers-logbook`, which is pushed to `main` here.
- **Accomplishments**:
  - Brand tokens in `assets/brand/tokens.json` with measured contrast, pixel icons and the Keeper 5x8 font; every palette (Python, iOS, demo, terminal, Tk, Android) is held to the tokens by drift tests (NFR-005).
  - The panel layout v2 with shared pixel vectors (`spec/panel_vectors.json`, 237 cases), drawn identically by Python, the C++ `panel_bitmap` and the demo's `web/panel/panel.js` (FR-016).
  - The spoken form for screen readers (`spec/spoken_vectors.json`, FR-017) and the iOS glance timeline core for widgets (FR-019). ADR-0011 (screen text v2) is Proposed.
  - CLI and config rework (`config.py`, `--watch` terminal frame, exit codes 2 and 130, stamped PNG and BMP), Home Assistant payload v2 with a fourth sensor (Last reading), SVG panel edge and per-image ids.
  - iOS glance and settings rework (hierarchy, URGENT band, STALE struck `last:` line, setup card, Check connection, fetch generation guard).
  - demo.html v2 with the real panel pixels; the ESP32 skeleton for the bench S3 and the X4 (NO DATA over serial, build only).
  - The desktop window (`python -m lightkeeper.desktop`, installed as `lightkeeper-window`, D12 pending) and the Android companion app (`apps/android`, the firmware's C++ through JNI).
  - Docs for waves 1 and 2 (a reviewed docs pass): SAFETY hazards HAZ-014 to HAZ-019, PRD and traceability, TEST_PLAN gaps GAP-007 to GAP-012, wiki. The roadmap gained further-out hardware ideas (a car dashboard box, big signs, a departure-board ticker).
- **Verification Run** (on the merged branch, 2026-10-28): Python 2,090 passed, 2 skipped, 100.00% line and branch coverage, ruff and strict mypy clean, 0 layer violations, 18 requirements traced; firmware 294 + 2,970 + 2,744 checks under ASan and UBSan in WSL, 17,600 fuzzed bodies; Swift package 75 tests; Node 14 of 14; PlatformIO `bench_s3` and `x4` build; Android offline Gradle build, 82 JVM tests and lint pass, and 39 instrumented tests passed on an API 36 emulator (run by the LK-11 fixer through adb). Not run anywhere yet: `android.yml`, `firmware-device.yml`, the SwiftUI app build in `ios.yml` on these changes, any physical panel, a real Home Assistant, a real phone.
- **Still running when this was pushed**: a wave 3 docs pass (FR-018 for the desktop window, FR-020 for Android, hazard citations and review triggers, OTS rows for the Android build dependencies, README, wiki) and a cross-batch adversarial review with fixes. Their branches (`docs3/integrated`, `review/<area>`) start from `4a12cf6` and still need merging.
- **Known Blockers**: Eric's decisions D1 to D17 and the open questions (listed for the PR); Kaitlin's safety review; no Nightscout instance (GAP-003); no hardware (GAP-001, GAP-005).
- **Context Hints**: Workflow notes and per-item results live in the session scratchpad and are not in the repo. `core.autocrlf` is true here, so `git status` can show a file modified with no diff. Worktree agents cannot run `wsl`. Leftover folders under `.claude/worktrees/` need deleting by hand (long Android build paths). The demo inlines `pageBytes`, so any `demo.html` edit needs `python tools/gen_demo_panel.py`.

#### Next Steps

**Human action required:** steps 4, 5, 6, 7, 8, 9, 10, and 11.

1. [ ] **AUTOMATED** — CI runs on the push to `main`: the constitution workflows, `iOS` (first run of the reworked SwiftUI views and app tests), `Android` (first run), `Firmware device build` (first run) and `Demo page`
   - **Done when:** every workflow is green on the pushed commit, or each red one has a fix committed.
2. [ ] **AGENT** — Merge the wave 3 docs pass (`docs3/integrated`) and the cross-batch review fixes (`review/<area>`), resolving any overlap in `docs/ROADMAP.md`, `CHANGELOG.md` and `wiki/Roadmap.md` so both sides survive; rerun every suite and push
   - **Done when:** FR-018 and FR-020 are in the PRD and traceability, every confirmed review finding is fixed or explained, and CI is green.
3. [ ] **AGENT** — Propose the session's MEMORY.md learnings to Eric (Tk DPI awareness, Tcl wall-clock timers, real-Tk tests in a child process, offline Android instrumented tests through adb)
   - **Done when:** Eric has said yes or no to each and the approved ones are in `docs/MEMORY.md`.
4. [ ] **HUMAN** — Eric deletes the leftover folders in `C:\Projects\lightkeeper\.claude\worktrees\`
   - **Why a human:** the agent's delete was refused, and the Android build paths are too long for `git worktree remove`.
   - **Done when:** the folder is empty.
5. [ ] **HUMAN** — Eric reviews the batch's decisions and defaults: D1 brand tokens, D2 IN RANGE green, D3 stamps, D4 no headline wrap, D12 `lightkeeper-window`, D14 Home Assistant payload v2, the advice note under the terminal footer, iOS and Android refusing a sub-path, the 60,000-byte panel buffer, the Android application id and ABIs, and the new roadmap section
   - **Why a human:** product and brand choices belong to the owner.
   - **Done when:** each is approved or changed, and the approved ones are recorded in `docs/MEMORY.md`.
6. [ ] **HUMAN** — Eric and Kaitlin approve the spoken sentences and decide ADR-0011
   - **Why a human:** the safety reviewer signs off on wording.
   - **Done when:** the decision is in `docs/SAFETY_REVIEW.md` and ADR-0011 is Accepted or Rejected.
7. [ ] **HUMAN** — Kaitlin reviews `docs/SAFETY.md` and the default thresholds
   - **Why a human:** thresholds and the safety boundary are her call, with her care team.
   - **Done when:** Kaitlin has filled in and signed `docs/SAFETY_REVIEW.md`, and the thresholds in `docs/ENV_VARS.md` are confirmed or changed to match.
8. [ ] **HUMAN** — Choose Nightscout hosting and deploy it (Phase 1)
   - **Why a human:** needs accounts, a domain, and a secret only Eric should hold.
   - **Done when:** Nightscout is reachable over HTTPS and a readable-role token exists.
9. [ ] **HUMAN** — Buy the Tier 1 hardware in `docs/HARDWARE.md`, and confirm the bench board's flash size and pins (marked VERIFY in `firmware/xteink/README.md`)
   - **Why a human:** a purchase, physical checks, and flashing risks bricking a board.
   - **Done when:** the bench board prints its NO DATA panel over USB with the CRC-32 the README gives.
10. [ ] **HUMAN** — Set up the Mosquitto add-on and a broker user in Home Assistant, then point a display at it
    - **Why a human:** it needs the household's Home Assistant and a broker password.
    - **Done when:** the four Lightkeeper sensors appear, and stopping the publisher shows `unavailable` (closes GAP-002).
11. [ ] **HUMAN** — Try the Android debug APK and the desktop window on a real phone and a Mac
    - **Why a human:** it needs Eric's devices.
    - **Done when:** both show the same screen as the demo for the same reading, and a Mac window is crisp on Retina.
12. [ ] **AUTOMATED** — `check_constitution_freshness.sh` flags when the pinned `constitution/` submodule needs re-pinning; dependabot opens the bump PR
    - **Done when:** the freshness check passes.

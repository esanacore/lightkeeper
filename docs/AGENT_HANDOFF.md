# Agent Handoff

This document helps transition work between AI agent sessions or between agents.

**Before starting your session**, check `docs/SESSION_PLAN.md` for planned work and `docs/MEMORY.md` for durable learnings. Read `docs/SAFETY.md` before touching anything in `src/`.

Replace the entry below at the end of every push; only the latest handoff is kept. `constitution/scripts/check_next_steps.sh` checks the procedure's format.

## Latest Handoff

### Session: 2026-10-27 to 2026-10-29 (Keeper's Logbook batch: UX and more platforms)
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
  - Docs for wave 3 (a second reviewed docs pass): FR-018 (desktop window) and FR-020 (Android) with acceptance criteria and traceability, both surfaces in the hazard log, security model and test plan (GAP-013 to GAP-015), OTS rows for the Android build, README, CHANGELOG and wiki.
  - A cross-batch adversarial review: 4 finders, a skeptic per finding, then a fixer per area. 17 of 20 findings were confirmed and all 17 are fixed. The 3 refuted ones are recorded as open questions in `TODO.md`. The four major ones:
    - The always-on stamp could push the age line down to scale 1, or outgrow the status, on unusual panel sizes. It is now chrome in Python, JS and C++, and the pinned CRCs are unchanged.
    - The iOS panel preview did not strike STALE's `last:` line.
    - The desktop `--demo` age line flipped back a minute every minute.
    - The three real-Tk tests silently skipped on CI. The Test Runner now runs under `xvfb-run`, and those tests fail on CI rather than skip.
  - Smaller fixes:
    - the demo phone mock now matches the apps;
    - `NIGHTSCOUT_URL` parse errors no longer echo the address;
    - failed answers close their connection;
    - `lightkeeper-window` shows configuration errors in a plain window;
    - Dependabot watches Gradle, and the firmware build has a timeout;
    - the Ctrl+C Home Assistant tests no longer race the fourth sensor's packet.
- **Verification Run** (on the merged branch, 2026-10-29): 
  - Python: 2,110 passed and 2 skipped, both named (the POSIX-only time-zone test and the Unix datagram test). Line and branch coverage is 100.00% (2,191 statements, 568 branches). ruff, ruff format and strict mypy are clean.
  - Python again on CPython 3.15.2 with Tk 9.0.4, after the developer machine lost CPython 3.14 (pytest 9.2, ruff 0.17.3, mypy 2.4.1): the same 2,110 pass, the three real-Tk tests included, at 100.00% line and branch, and ruff and mypy are clean. The desktop window now has passing tests on Tk 8.6 (Windows, and Linux under Xvfb in CI) and on Tk 9.0 (Windows).
  - Constitution checks: 0 layer violations; 20 requirements traced, 20 covered; the demo page, README, wiki links, environment variables, OTS inventory, secrets and Next Steps checks pass.
  - Firmware in WSL, under ASan and UBSan: 294, 2,970 and 2,753 checks, with 17,600 fuzzed bodies.
  - Swift package: 76 tests.
  - Node: 15 of 15.
  - PlatformIO: `bench_s3` and `x4` build.
  - Android: the offline Gradle build passes 82 JVM tests and lint, and the debug APK is 1,060,459 bytes. The instrumented tests were not rerun locally (only comments and assertions changed in Kotlin); CI runs them.
  - Not run anywhere yet: any physical panel, a real Home Assistant, a real phone, macOS.
- **CI so far**:
  - On `main` at `1c0cdb8`, every workflow passed except one Android instrumented test, which the default emulator screen was too narrow for: iOS (the reworked SwiftUI views and app tests on the simulator for the first time), Firmware device build (first run), the Constitution Test Runner and every constitution check, and Demo page.
  - `5113fb5` moved the emulator to a Pixel 6 screen, and `android.yml` went green with all 39 instrumented tests (run 40992168914).
  - On `main` at `cffa025` (the merged docs pass and review fixes) every workflow passed. The Test Runner ran under `xvfb-run`, Tk 8.6 opened a window, and 2,112 tests passed with none skipped (run 41001677074).
- **Known Blockers**: Eric's decisions D1 to D17 and the open questions (listed in `TODO.md`); Kaitlin's safety review; no Nightscout instance (GAP-003); no hardware (GAP-001, GAP-005).
- **Context Hints**:
  - Workflow notes and per-item results live in the session scratchpad and are not in the repo.
  - `core.autocrlf` is true here, so `git status` can show a file modified with no diff.
  - Worktree agents cannot run `wsl`.
  - Leftover folders under `.claude/worktrees/` need deleting by hand (long Android build paths).
  - The demo inlines `pageBytes`, so any `demo.html` edit needs `python tools/gen_demo_panel.py`.
  - The batch was pushed straight to `main`, so `ux/keepers-logbook` and `main` hold the same commits and there is no batch pull request; the decisions live in `TODO.md`.

#### Next Steps

**Human action required:** steps 4, 5, 6, 7, 8, 9, 10, 11, and 12.

1. [ ] **AUTOMATED** — CI runs on this docs-only push to `main`. Every workflow already passed on `cffa025`, which held all the code: the Test Runner under `xvfb-run` (2,112 tests, none skipped), iOS with the struck panel preview, and Android and the firmware build with the new stamp rule.
   - **Done when:** every workflow is green on the pushed commit.
2. [x] **AGENT** — Record on GAP-015 that the real-Tk tests passed on Linux under a virtual display. macOS, a real Linux display with several monitors, and a real clock change stay open.
   - **Done when:** `docs/TEST_PLAN.md` GAP-015, its coverage row, `TODO.md`, the OTS row and the wiki say what CI showed. Done on 2026-10-29.
3. [x] **AGENT** — Propose the session's MEMORY.md learnings to Eric: Tk DPI awareness, Tcl's wall-clock `after()` timers, real-Tk tests in a child process, offline Android instrumented tests through adb, JDK 24 locally against Temurin 21 in CI, and a broker test waiting for every packet
   - **Done when:** Eric has said yes or no to each, and the approved ones are in `docs/MEMORY.md`. Done on 2026-10-29: Eric approved all six, and they are under Codebase Learnings & Gotchas.
4. [ ] **HUMAN** — Eric deletes the leftover folders in `C:\Projects\lightkeeper\.claude\worktrees\`: `wf_4bb1f8cd-5c6-3`, `wf_4e278c17-9d7-6` to `-8`, and `wf_2b0dc469-d0f-9`.
   - **Why a human:** the agent's delete was refused, and the Android build paths are too long for `git worktree remove`.
   - **Done when:** the folder is empty.
5. [ ] **HUMAN** — Eric reviews the batch's decisions, defaults and open questions in `TODO.md`:
   - D1 brand tokens, D2 IN RANGE green, D3 stamps, D4 no headline wrap;
   - D12 `lightkeeper-window`, and its new error window;
   - D14 Home Assistant payload v2;
   - the advice note under the terminal footer;
   - iOS and Android refusing a sub-path;
   - the 60,000-byte panel buffer;
   - the Android application id and ABIs;
   - a SIMULATED mark on the desktop `--demo`;
   - one NO DATA frame and STALE hatch across screens;
   - the new roadmap section.
   - **Why a human:** product and brand choices belong to the owner.
   - **Done when:** each is approved or changed, and the approved ones are recorded in `docs/MEMORY.md`.
6. [ ] **HUMAN** — Eric decides whether to protect `main`, which needs pull requests and passing checks before a merge.
   - **Why a human:** it is a GitHub repository setting on Eric's account, and the batch was pushed straight to `main` with his say-so.
   - **Done when:** `main` is protected, or Eric has said direct pushes stay allowed.
7. [ ] **HUMAN** — Eric and Kaitlin approve the spoken sentences and decide ADR-0011
   - **Why a human:** the safety reviewer signs off on wording.
   - **Done when:** the decision is in `docs/SAFETY_REVIEW.md` and ADR-0011 is Accepted or Rejected.
8. [ ] **HUMAN** — Kaitlin reviews `docs/SAFETY.md` and the default thresholds
   - **Why a human:** thresholds and the safety boundary are her call, with her care team.
   - **Done when:** Kaitlin has filled in and signed `docs/SAFETY_REVIEW.md`, and the thresholds in `docs/ENV_VARS.md` are confirmed or changed to match.
9. [ ] **HUMAN** — Choose Nightscout hosting and deploy it (Phase 1)
   - **Why a human:** needs accounts, a domain, and a secret only Eric should hold.
   - **Done when:** Nightscout is reachable over HTTPS and a readable-role token exists.
10. [ ] **HUMAN** — Buy the Tier 1 hardware in `docs/HARDWARE.md`, and confirm the bench board's flash size and pins (marked VERIFY in `firmware/xteink/README.md`)
   - **Why a human:** a purchase, physical checks, and flashing risks bricking a board.
   - **Done when:** the bench board prints its NO DATA panel over USB with the CRC-32 the README gives.
11. [ ] **HUMAN** — Set up the Mosquitto add-on and a broker user in Home Assistant, then point a display at it
    - **Why a human:** it needs the household's Home Assistant and a broker password.
    - **Done when:** the four Lightkeeper sensors appear, and stopping the publisher shows `unavailable` (closes GAP-002).
12. [ ] **HUMAN** — Try the Android debug APK and the desktop window on a real phone and a Mac
    - **Why a human:** it needs Eric's devices.
    - **Done when:** both show the same screen as the demo for the same reading, and a Mac window is crisp on Retina.
13. [ ] **AUTOMATED** — `check_constitution_freshness.sh` flags when the pinned `constitution/` submodule needs re-pinning; dependabot opens the bump PR
    - **Done when:** the freshness check passes.

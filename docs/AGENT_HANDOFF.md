# Agent Handoff

This document helps transition work between AI agent sessions or between agents.

**Before starting your session**, check `docs/SESSION_PLAN.md` for planned work and `docs/MEMORY.md` for durable learnings. Read `docs/SAFETY.md` before touching anything in `src/`.

Replace the entry below at the end of every push; only the latest handoff is kept. `constitution/scripts/check_next_steps.sh` checks the procedure's format.

## Latest Handoff

### Session: 2026-10-27 to 2026-11-01 (Keeper's Logbook batch, then Eric's decisions)
- **Goal**: Eric asked to sharpen what exists, build out more platforms, and bring the UI up to what industry leaders do, with a home-grown, lo-fi look that suits an open-source project. The result is "Keeper's Logbook, 1-bit edition", built in three waves of items (LK-01 to LK-11), each built in its own worktree, reviewed adversarially, fixed, and pushed to `main`. On 2026-11-01 Eric answered the batch's open decisions.
- **Accomplishments**:
  - Brand tokens in `assets/brand/tokens.json` with measured contrast, pixel icons and the Keeper 5x8 font; every palette (Python, iOS, demo, terminal, Tk, Android) is held to the tokens by drift tests (NFR-005).
  - The panel layout v2 with shared pixel vectors (`spec/panel_vectors.json`, 237 cases), drawn identically by Python, the C++ `panel_bitmap` and the demo's `web/panel/panel.js` (FR-016).
  - The spoken form for screen readers (`spec/spoken_vectors.json`, FR-017) and the iOS glance timeline core for widgets (FR-019). ADR-0011 (screen text v2) is Proposed.
  - CLI and config rework, Home Assistant payload v2 with a fourth sensor, the iOS glance and settings rework, demo.html v2 with the real panel pixels, and the ESP32 skeleton for the bench S3 and the X4.
  - The desktop window (`python -m lightkeeper.desktop`, installed as `lightkeeper-window`) and the Android companion app (`apps/android`, the firmware's C++ through JNI).
  - Two reviewed docs passes (FR-018 and FR-020, the hazard log, security model, test plan, OTS inventory, wiki), and a cross-batch adversarial review whose 17 confirmed findings are all fixed.
  - Eric's decisions (2026-11-01), recorded in `TODO.md` with the date:
    - 36 open decisions closed, among them D1, D2, D3, D8, D9, D12, D14, D15 and D17, the Android defaults, the desktop window, SVG and demo defaults, and the widget defaults.
    - New work they created: iOS signing and TestFlight (D10), IBM Plex Mono on every screen (D13), a per-board firmware panel buffer, and an LGPL release note.
    - The firmware panel driver will be home-grown (D11), keeping the firmware Apache-2.0.
    - Nightscout goes on ElfHosted: ADR-0012, Accepted.
    - 20 docs no longer call these choices pending.
  - The leftover worktree folders are deleted, at Eric's request.
- **Verification Run** (2026-11-01, Windows 11, CPython 3.15.2 with Tk 9.0.4): 
  - Python: 2,110 passed and 2 skipped, both named (the POSIX-only time-zone test and the Unix datagram test), at 100.00% line and branch coverage (2,191 statements, 568 branches). The three real-Tk tests passed.
  - Constitution checks: wiki links, README, demo page, compliance, environment variables, OTS inventory, secrets and Next Steps pass, and 20 of 20 requirements are traced.
  - This push changes only docs, so the firmware, Swift, Node, PlatformIO and Android results from 2026-10-29 still stand.
- **CI so far**: every workflow passed on `main` at `cffa025` (all the batch's code) and on the docs-only pushes after it, up to `4bb0b72`. The Test Runner runs under `xvfb-run`, so the three real-Tk tests run on Linux.
- **Known Blockers**:
  - Kaitlin's items: D4 to D7, D16, an upper bound for `LK_STALE_MINUTES`, the hazard severities and her safety review.
  - The iOS URGENT band, decided on a device once TestFlight works.
  - D11's CA certificate fetch and the X4's panel controller.
  - No Nightscout instance yet (GAP-003), and no hardware (GAP-001, GAP-005).
- **Context Hints**:
  - `core.autocrlf` is true here, so `git status` can show a file modified with no diff.
  - Worktree agents cannot run `wsl`.
  - The demo inlines `pageBytes`, so any `demo.html` edit needs `python tools/gen_demo_panel.py`.
  - CPython 3.14 is gone from this machine: base local venvs on `C:\Users\esana\AppData\Local\Python\pythoncore-3.15-64\python.exe`. The session temp folder can be cleared between days, venvs included.
  - Eric chose to protect `main`. Once he has turned it on, changes go through pull requests, not direct pushes.

#### Next Steps

**Human action required:** steps 2, 3, 6, 9, 10, 11, and 12.

1. [ ] **AUTOMATED** — CI runs on the push that records Eric's decisions.
   - **Done when:** every workflow is green on the pushed commit.
2. [ ] **HUMAN** — Eric protects `main` on GitHub. Under Settings, Branches, add a classic branch protection rule for `main`: require a pull request before merging, and require the checks that run on every pull request to pass (the Constitution Test Runner and the other Constitution workflows). Android, iOS and Firmware device build run only when their paths change, so a pull request that does not touch them would wait forever if they were required.
   - **Why a human:** it is a repository setting on Eric's GitHub account.
   - **Done when:** a direct push to `main` is refused. From then on, agents open pull requests.
3. [ ] **HUMAN** — Eric starts the ElfHosted trial (ADR-0012) and runs the trial checks. A `readable` token in the `api-secret` header returns entries, a request with no credentials gets 401, and the site sits at a root address.
   - **Why a human:** it needs Eric's account, payment and the `API_SECRET`, which only he should hold.
   - **Done when:** the three checks pass and the readable token works with `python -m lightkeeper`.
4. [ ] **AGENT** — Write the exact ElfHosted steps in `docs/SETUP.md` Phase 1, from Eric's trial notes, and record its backup retention in `docs/OPERATIONS.md`.
   - **Done when:** `TODO.md`'s deployment-steps item is ticked.
5. [ ] **AGENT** — Build Kaitlin's review packet: a private, shareable page with each of her questions, its default, the evidence (screens, sentences, contact sheets) and a place to answer.
   - **Done when:** Eric has the link to send her.
6. [ ] **HUMAN** — Kaitlin works through the packet (D4 to D7, D16, the `LK_STALE_MINUTES` bound, the hazard severities, the thresholds and `docs/SAFETY.md`) and signs `docs/SAFETY_REVIEW.md`.
   - **Why a human:** thresholds, wording and the safety boundary are her call, with her care team.
   - **Done when:** `docs/SAFETY_REVIEW.md` is signed and ADR-0011 is Accepted or Rejected.
7. [x] **AGENT** — Propose a `docs/MEMORY.md` entry for the 2026-11-01 decisions, and record it once Eric approves the text.
   - **Done when:** the entry is under Active Project Decisions. Done on 2026-11-01: Eric approved it.
8. [ ] **AGENT** — Do the work the decisions created:
   - IBM Plex Mono on every screen, asking Eric before each download with the file's name, source and size;
   - the per-board firmware panel buffer;
   - the LGPL release note;
   - the iOS signing, App Group and TestFlight setup.
   - **Done when:** each `TODO.md` item is ticked, with tests where code changed.
9. [ ] **HUMAN** — Eric does the Apple steps that need his login: the App ID and App Group in the developer portal, and the TestFlight upload. Then he checks the glance on his iPhone (GAP-009) and decides the iOS URGENT band.
   - **Why a human:** it needs Eric's Apple Developer account and his phone.
   - **Done when:** a TestFlight build runs on his iPhone and the URGENT band item is decided.
10. [ ] **HUMAN** — Eric buys the Tier 1 hardware in `docs/HARDWARE.md` and confirms the bench board's flash size and pins (marked VERIFY in `firmware/xteink/README.md`).
    - **Why a human:** it is a purchase, a physical check, and flashing risks bricking a board.
    - **Done when:** the bench board prints its NO DATA panel over USB with the CRC-32 the README gives.
11. [ ] **HUMAN** — Eric sets up the Mosquitto add-on and a broker user in Home Assistant, then points a display at it.
    - **Why a human:** it needs the household's Home Assistant and a broker password.
    - **Done when:** the four Lightkeeper sensors appear, and stopping the publisher shows `unavailable` (closes GAP-002).
12. [ ] **HUMAN** — Eric tries the Android debug APK on a real phone and the desktop window on a Mac.
    - **Why a human:** it needs Eric's devices.
    - **Done when:** both show the same screen as the demo for the same reading, and the Mac window is crisp on Retina.
13. [ ] **AUTOMATED** — `check_constitution_freshness.sh` flags when the pinned `constitution/` submodule needs re-pinning, and Dependabot opens the bump pull request.
    - **Done when:** the freshness check passes.

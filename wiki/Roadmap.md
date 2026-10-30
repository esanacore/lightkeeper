# Roadmap

How Lightkeeper grows and the rules for growing it. The source documents are `docs/ROADMAP.md` (the shape), `docs/MVP_BACKLOG.md` (the checklist for each phase), and `TODO.md` (individual work items) in the repository. Phases gate on evidence, not dates.

## The one rule

Lightkeeper grows outward from Nightscout, never inward toward the pump or the sensor. New features are new ways to see data, new places to see it, or new ways to ask an established controller (Trio) to do something within its own limits. ADR-0004 and ADR-0008 define that boundary, and moving it takes a new ADR, a hazard review, and the agreement of the person whose data it shows. See [[Safety]] and [[Architecture Decisions]].

## Phases

| Phase | Scope | Exit evidence | Owner | Status |
| --- | --- | --- | --- | --- |
| 0 Foundation | Repository, safety boundary, display rules in Python and C++, docs, CI | Suite green; hazards logged; thresholds reviewed by the person with diabetes | Eric | Code and docs done; threshold review open |
| 1 Data hub | Self-hosted Nightscout over HTTPS, readable token, backups | Trio uploads; one restore tested; `lightkeeper` reads real data | Eric | Not started |
| 2 Open loop | Trio on the primary iPhone with Omnipod 5 pods, suggestions only | Two weeks of logs; settings validated with the endocrinologist | The person with diabetes and their care team | Not started |
| 3 Closed loop | Trio automates; weekly review at first | ADR-0002 promotion criteria met | The person with diabetes and their care team | Not started |
| 4 Displays | Bedside e-ink on a Pi, Xteink pocket firmware, Home Assistant sensor and alerts, a desktop window | One full sensor session beside the primary app, no mismatch, freeze, or missed STALE | Eric builds; the person with diabetes decides whether to rely on it | C++ rules, response parser and panel rasterizer done; a build-only ESP32 skeleton prints NO DATA over serial; a desktop window shows the real panel pixels (checked on Windows 11); hardware not yet bought |
| 5 Companion app | Read-only iOS app first, and a read-only Android app; bolus requests through Trio's remote protocol second | ADR-0008 promotion criteria met; TestFlight; hazard analysis for the bolus screen | The person with diabetes decides; Eric runs the hazard review | Read-only iOS layer builds and tests in CI, with the reworked glance and the widget timeline core; nothing on TestFlight. A read-only Android app, tested on an emulator, sideloaded, not yet on a phone |
| 6 Community | Published demo, PyPI package, contributor guide, other CGM and controller setups | Someone outside the household runs a display beside their own primary app and reports back | Eric | Not started |

Phases 1 to 3 are about the therapy half and belong to the person with diabetes and their care team; [[Nightscout and Trio Setup]] covers them. Phases 4 to 6 are where this repository's engineering goes. Phases can overlap: display work does not wait for closed loop.

## How a new feature gets in

1. **Name the requirement.** Add an `FR-` or `NFR-` entry with acceptance criteria to `docs/PRODUCT_REQUIREMENTS.md`. Unstarted work sits in the Planned section so the traceability gate stays honest; it is promoted in the same change that adds its first verifying test.
2. **Check the boundary.** Reading and showing data is in scope. Asking Trio to do something goes through Trio's remote protocol and gets a hazard entry first. Touching the pump or sensor means stop and write an ADR; the default answer is no.
3. **Change the rules in one commit.** Display behavior lives in the Python package, the C++ rules, the Swift core, and `spec/display_vectors.json`, and they must agree. Then `python tools/gen_display_gallery.py` refreshes the gallery and the demo. [[Contributing]] has the details.
4. **Add the hazard.** Anything that changes what a person sees gets a row in `docs/SAFETY.md` with a mitigating test.
5. **Keep the docs current.** README, CHANGELOG, TODO, the OTS inventory, and this wiki.
6. **Run the suite and the constitution checks.** [[Testing and Quality]] has the commands; CI runs them on every push.

[[Community Research]] feeds this roadmap through its twelve implications: data age as the primary element, a real night profile, secrets handling as a differentiator, connectivity honesty, and "secondary awareness" wording rather than "alarm".

## Reserved requirements and likely next additions

Five requirement IDs are reserved, each with acceptance criteria already written: FR-007 (Raspberry Pi e-paper adapter; its rasterizer and service are done, the panel driver waits for hardware), FR-010 (Xteink device build), FR-013 (mmol/L display, thresholds entered in the same unit, vectors covering both units), FR-014 (signed delta beside the arrow), and FR-015 (battery level and time since the display last reached Nightscout, visible without hiding the glucose line). FR-008, Home Assistant, was promoted and built in October 2026 (ADR-0010). FR-016 (panel pixels), FR-017 (spoken form), FR-019 (the glance timeline) and NFR-005 (brand tokens) were added with the Keeper's Logbook work in October 2026, and FR-018 (the desktop window) and FR-020 (the Android app) in its third wave.

In rough order:

- Nightscout deployment notes and a real-instance end-to-end test, closing GAP-003.
- Hardware from [[Hardware]]: the Pi Zero 2 WH with a 2.9 inch e-paper HAT, then the Xteink X4 Pro and the ESP32-S3 bench board.
- The Pi e-paper panel driver (FR-007), and a check of the Home Assistant integration against a real install (GAP-002).
- The Xteink device build (FR-010): the panel rasterizer and a build-only skeleton exist; next are Wi-Fi and the panel driver. See [[Firmware]].
- Screen text v2 (ADR-0011), after its hazard review and sign-off.
- Graded aging before STALE (needs a vector change and a hazard review), and distinguishing "phone stopped uploading" from "Nightscout unreachable" via Nightscout's device status.
- mmol/L, delta, device status, IOB and COB greyed at zero, and a night profile.
- Companion app extras (widgets, watch complication, background refresh), then the bolus request screen once ADR-0008 is accepted; the widget timeline core is done and the extension waits on Apple signing. See [[Companion App]].
- The Android app on a real phone (API 26 to 36, with TalkBack; GAP-013), then its follow-ups: Check connection, TalkBack's spoken sentences, a widget once the exact-alarm decision is made, and release signing.
- The desktop window off Windows: on macOS (whether the panel stays sharp on a Retina display), on a real Linux display (CI already runs its real-window tests on a virtual one), and against a system clock set back by hand (GAP-015).
- PyPI release (Phase 6); the demo page is already published.

## Further out: more places to see it

Once the first Phase 4 devices have earned trust, Lightkeeper should grow into more hardware. Each idea is a new place to see the same data, so it sits inside the one rule. None has a requirement ID yet, and each comes in the way any feature does. `docs/ROADMAP.md` lists what each one has to solve.

- **A dashboard box for the car**: a small e-paper box with a solar panel on top. It must never ask for attention while the car moves, it has to survive a car parked in the sun, and it must go STALE on time when the link drops on the road.
- **Big signs**: a large panel readable across a kitchen or hallway. A big sign shows someone's glucose to anyone walking past, so it belongs in rooms the household controls, with a way to blank it and a real night profile.
- **A departure-board ticker**: a long, thin split-flap or LED dot-matrix board like the ones at train and bus stations. It changes once per reading and never scrolls, a split-flap board must not clatter at night, and its short lines need their own compact screen text and a hazard review.
- **And more**: the test for each is the same. Does it show the data honestly, say plainly when the data is old, and stay quiet?

## Versioning

Semantic versioning; `VERSION`, `pyproject.toml`, and `lightkeeper.__version__` all read 0.2.0, tagged `v0.2.0` on 2026-10-27 (0.1.0 was tagged 2026-10-24). The display vectors carry their own `spec_version` (currently 1): a change to an existing case bumps it, adding a case does not, and all three implementations and the Android app's instrumented tests assert it, so a vector change cannot be silently ignored by one port. `spec/panel_vectors.json` has its own `panel_spec_version` (currently 1). Token-in-query-string debt is noted in [[Security and Privacy]].

Back to [[Home]].

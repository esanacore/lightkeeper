# Roadmap

How Lightkeeper grows, and the rules for growing it. `docs/MVP_BACKLOG.md` tracks the checklist for each phase; `TODO.md` holds individual work items. This document explains the shape.

## The one rule

Lightkeeper grows outward from Nightscout, never inward toward the pump or the sensor. New features are new ways to see data, new places to see it, or new ways to ask an established controller (Trio) to do something within its own limits. ADR-0004 and ADR-0008 define that boundary, and moving it takes a new ADR, a hazard review, and Kaitlin's agreement.

## Phases

| Phase | Scope | Exit evidence | Owner of the decision |
| --- | --- | --- | --- |
| 0 Foundation | Repository, safety boundary, display rules in Python and C++, docs, CI | Suite green; hazards logged; Kaitlin reviews thresholds | Eric |
| 1 Data hub | Self-hosted Nightscout over HTTPS, readable token, backups | Trio uploads; one restore tested; `lightkeeper` reads real data | Eric |
| 2 Open loop | Trio on Kaitlin's iPhone with Omnipod 5 pods, suggestions only | Two weeks of logs; settings validated with her endocrinologist | Kaitlin with her care team |
| 3 Closed loop | Trio automates; weekly review at first | ADR-0002 promotion criteria met | Kaitlin with her care team |
| 4 Displays | Bedside e-ink on a Pi, Xteink pocket firmware, Home Assistant sensor and alerts | One full sensor session side by side with the primary app, no mismatch, freeze, or missed STALE | Eric builds, Kaitlin decides whether to rely on it |
| 5 Companion app | Read-only iOS app first; bolus requests through Trio's remote protocol second | ADR-0008 promotion criteria met; TestFlight; hazard analysis for the bolus screen | Kaitlin decides, Eric runs the hazard review |
| 6 Community | Published demo, PyPI package, contributor guide, other CGM and controller setups | Someone outside the household runs a display beside their own primary app and reports back | Eric |

Phases 1 to 3 are mostly about the therapy half and belong to Kaitlin and her care team. Phases 4 to 6 are where this repository's own engineering goes. Phases can overlap: display work does not wait for closed loop.

## How a new feature gets in

1. **Name the requirement.** Add an `FR-` or `NFR-` entry with acceptance criteria to `docs/PRODUCT_REQUIREMENTS.md`. Unstarted work sits in the Planned section so the traceability gate stays honest.
2. **Check the boundary.** If the feature reads data and shows it, it is in scope. If it asks Trio to do something, it goes through Trio's remote protocol and gets a hazard entry first. If it would touch the pump or sensor, stop and write an ADR; the default answer is no.
3. **Change the rules in one commit.** Display behavior lives in four places that must agree: `src/lightkeeper`, `firmware/xteink/lib/glucose_rules`, `apps/ios/LightkeeperCore`, and `spec/display_vectors.json`. A rule change updates all three, then `python tools/gen_display_gallery.py` refreshes the gallery and the demo. The panel's pixels have their own source of truth: a layout change regenerates `spec/panel_vectors.json` with `python tools/gen_panel_spec.py`, and the C++ rasterizer and the demo's JavaScript port must match it (FR-016). The spoken sentences follow the vectors through `python tools/gen_spoken_vectors.py` (FR-017).
4. **Add the hazard.** Anything that changes what a person sees gets a row in `docs/SAFETY.md` with a mitigating test.
5. **Keep the docs current.** README content, CHANGELOG, TODO, the OTS inventory for any new dependency, and the wiki if the shape of the project changed. The README's structure is fixed; only its content moves.
6. **Run the suite and the constitution checks.** `docs/TEST_PLAN.md` has the one command; CI runs it on every push.

## What the community told us

`docs/COMMUNITY_RESEARCH.md` collects what people like and dislike about existing displays, follower apps, and bedside devices. Its twelve implications feed this roadmap: data age as the primary element, a real night profile, secrets handling as a differentiator, connectivity honesty, and "secondary awareness" wording rather than "alarm".

## Likely next additions, in rough order

- Nightscout deployment notes and a real-instance end-to-end test (closes GAP-003).
- Hardware per `docs/HARDWARE.md`: Pi Zero 2 WH with a 2.9" e-paper HAT first, then the Xteink X4 Pro and an ESP32-S3 bench board.
- Raspberry Pi e-paper panel driver for the bedside display (FR-007). The rasterizer and the hardened systemd service are done; the SPI driver waits for the parts. The panel layout draws at six sizes and exported PNG and BMP images carry a stamp; whether the physical panel shows the stamp is Eric's call.
- Home Assistant against a real install (FR-008 is built and tested against a fake broker; GAP-002).
- Xteink device build (FR-010): the panel rasterizer and a build-only skeleton exist; next Wi-Fi, HTTPS, the panel driver (a choice Eric makes between a home-grown SSD16xx driver and GxEPD2) and deep sleep with real data.
- Optional mmol/L display units, and a delta from the previous reading.
- Companion app extras (widgets, watch complication, background refresh); the read-only layer (Phase 5a) builds and is tested in CI, and the glance timeline core that widgets will draw from is done (FR-019); the widget extension waits on Apple signing and App Groups. Then the bolus request screen (Phase 5b).
- Screen text v2 (ADR-0011), once its hazard review is done and Eric and Kaitlin have signed it off.
- PyPI release (Phase 6). The demo page is already published at https://esanacore.github.io/lightkeeper/.

## Further out: more places to see it

Once the first devices from Phase 4 have earned trust, Lightkeeper should grow into more hardware. Each idea below is a new place to see the same data, so it sits inside the one rule. None has a requirement ID yet; each gets one in the Planned section when work on it starts, and each comes in the way any feature does (above), with its parts in `docs/HARDWARE.md` and the shared display and panel vectors running on its renderer. Eric decides the order; the person with diabetes decides whether to rely on each one.

- **A dashboard box for the car.** A small e-paper box on the dashboard, with a solar panel on top to keep it charged. E-paper suits it: it reads well in sunlight and draws power only when the picture changes. What it has to solve:
  - It must never ask for attention while the car moves: no alerts, no motion, nothing to press. It must not block the view, a mirror or an airbag. The primary CGM app stays the thing to act on.
  - A car parked in the sun gets hotter inside than most batteries and panels are rated for, and lithium cells must not charge when hot. It needs parts rated for that heat, a charger that stops when the cell is too hot, and a plan for winter cold.
  - It reads through the phone's hotspot or the car's Wi-Fi, and on the road the link drops often. Going STALE on time and saying `Nightscout unreachable` matter even more there.
  - When the battery runs flat, e-paper keeps its last picture. The box must draw its "not updating" screen before it sleeps (HAZ-014).
- **Big signs.** A large panel for a kitchen or a hallway, readable across the room. The panel layout already draws any panel that holds every screen line, up to 4096 pixels a side, so the pixels exist and the work is the hardware. What it has to solve:
  - A big sign shows someone's glucose to everyone who walks past. It belongs in rooms the household controls, never facing a window, with an easy way to blank it.
  - A bright LED sign needs a real night profile: dim, or off.
  - The panel rules hold at every size: STALE is never weaker than a fresh reading, and the status word is never smaller than the number.
- **A departure-board ticker.** A long, thin board in the style of train and bus station signs, split-flap or LED dot matrix. It suits the 1-bit, lo-fi look. What it has to solve:
  - Nothing scrolls, blinks or ticks once a second. The board changes once per reading, the way a departures board updates a line, never as a scrolling marquee.
  - A split-flap board clatters when it changes, which breaks "no sound". It needs a quiet mechanism, or a night mode that holds still.
  - One or two short lines cannot hold today's screens. It needs a compact form of the screen text with its own display vectors and a hazard review, the same route as ADR-0011.
- **And more.** Other ideas will come. The test for each is the same: does it show the data honestly, say plainly when the data is old, and stay quiet?

## Versioning

Semantic versioning for the Python package and the repository as a whole. The display vectors carry their own `spec_version` inside `spec/display_vectors.json`; any change to an existing case bumps it, and all three implementations assert the version they were built against (`tests/test_vectors.py`, `firmware/xteink/test/host/test_glucose_rules.cpp`, `VectorTests.swift`). `spec/panel_vectors.json` carries its own `panel_spec_version` (currently 1): a change to the panel layout or its integer rules that alters an existing case's pixels bumps it (adding a case or a profile does not), and the Python, C++ and JavaScript renderers move together, each asserting the version (`tests/test_panel_vectors.py`, `firmware/xteink/test/host/test_panel_bitmap.cpp`, `web/panel/panel.test.mjs`).

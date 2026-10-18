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
3. **Change the rules in one commit.** Display behavior lives in three places that must agree: `src/lightkeeper`, `firmware/xteink/lib/glucose_rules`, and `spec/display_vectors.json`. A rule change updates all three, then `python tools/gen_display_gallery.py` refreshes the gallery and the demo.
4. **Add the hazard.** Anything that changes what a person sees gets a row in `docs/SAFETY.md` with a mitigating test.
5. **Keep the docs current.** README content, CHANGELOG, TODO, the OTS inventory for any new dependency, and the wiki if the shape of the project changed. The README's structure is fixed; only its content moves.
6. **Run the suite and the constitution checks.** `docs/TEST_PLAN.md` has the one command; CI runs it on every push.

## What the community told us

`docs/COMMUNITY_RESEARCH.md` collects what people like and dislike about existing displays, follower apps, and bedside devices. Its twelve implications feed this roadmap: data age as the primary element, a real night profile, secrets handling as a differentiator, connectivity honesty, and "secondary awareness" wording rather than "alarm".

## Likely next additions, in rough order

- Nightscout deployment notes and a real-instance end-to-end test (closes GAP-003).
- Raspberry Pi e-paper adapter for the bedside display (FR-007).
- Home Assistant integration: sensor entity plus example automations (FR-008).
- Xteink device build: Wi-Fi, HTTPS, JSON, e-paper, deep sleep (FR-010).
- Optional mmol/L display units, and a delta from the previous reading.
- Companion app, read-only layer (Phase 5a), then the bolus request screen (Phase 5b).
- PyPI release and a published demo page (Phase 6).

## Versioning

Semantic versioning for the Python package and the repository as a whole. The display vectors carry their own `spec_version` inside `spec/display_vectors.json`; any change to an existing case bumps it, and both implementations assert the version they were built against.

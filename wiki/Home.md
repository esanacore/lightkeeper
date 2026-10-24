# Lightkeeper

Current version: 0.1.0

Lightkeeper is an open source type 1 diabetes project, built by Eric for a household with T1D alongside the #WeAreNotWaiting community. It sits beside Nightscout and Trio and turns glucose data that Nightscout already has into calm, glanceable screens: a bedside e-ink panel, a pocket e-ink reader, an iOS companion app, and Home Assistant alerts. Everything in this repository is read-only. It never commands a pump, never talks to a sensor, and never writes to Nightscout. Insulin dosing stays in Trio, a mature community project, configured by the person with diabetes and their care team.

Repository: https://github.com/esanacore/lightkeeper (Apache-2.0).

## The one rule

Lightkeeper is a secondary display and not a medical device. Always confirm on the primary CGM app before acting.

Inside the code, that rule has a concrete form: old data is never shown as current. A reading older than 15 minutes, or dated more than 2 minutes in the future, shows **STALE - DO NOT TRUST**, even when the number would otherwise look alarming or reassuring. Staleness is checked before any range check, in every implementation, and a shared set of test vectors proves it. [[Safety]] explains the boundary, the intended use, and the hazard log behind it.

## Where to go, by who you are

**If you live with T1D, or care for someone who does**, and want to know whether a Lightkeeper screen can be trusted and what each state means:

- [[Safety]]: what Lightkeeper will never do, its limitations, and the hazards it guards against.
- [[Display States]]: a picture of every screen it can show, and the rules that produce them.
- [[Getting Started]]: install it, run the offline demo, point it at your Nightscout.
- [[Hardware]]: what to buy for a bedside or pocket display, and what to avoid.
- [[Nightscout and Trio Setup]]: the phased plan for the therapy half, with links to the community guides.
- [[Troubleshooting]] and [[FAQ]] for the questions that come up most.

**If you are a developer** who wants to run, extend, or port it:

- [[How It Works]]: the data flow, the layer boundaries, and the four places the rules live.
- [[Architecture Decisions]]: the eight ADRs in one page.
- [[Testing and Quality]]: the test pyramid, shared vectors, coverage floors, and how to run everything.
- [[Firmware]] and [[Companion App]]: the ESP32 and iOS ports.
- [[Contributing]]: commit conventions, the rule-change-in-one-commit requirement, and hazard review.

**If you are auditing the project** for quality or security practice:

- [[Safety]] and [[Security and Privacy]]: classification rationale, hazard log, data classification, STRIDE model, token handling.
- [[Testing and Quality]]: requirements traceability, coverage targets, the constitution CI checks.
- [[Architecture Decisions]]: status and promotion criteria for every decision.
- [[Roadmap]]: the phases, their exit evidence, and who owns each gate.

[[Glossary]] defines the terms used throughout, [[Brand]] covers the mark, palette, and voice, and [[Community Research]] records what people with T1D, partners, and parents said about existing displays and what Lightkeeper takes from it.

## Project status

Version 0.1.0 is Phase 0, the foundation, and has not yet been tagged. The Python display tool (`lightkeeper`) is complete for its first release: strict parsing, configurable thresholds, staleness and future-timestamp protection, four-line e-ink rendering, safe degradation when Nightscout fails, a CLI with demo mode, and an SVG panel renderer. The suite is 177 tests at 100% line and branch coverage against a 90% floor. The same rules exist in C++17 for the Xteink pocket display and in Swift for the iOS app, and all three implementations pass the 39 shared vectors in `spec/display_vectors.json` and assert its `spec_version`.

Not done yet: Nightscout is not deployed (Phase 1), Trio is not running on the primary phone (Phases 2 and 3), no physical e-paper panel has been driven (Phase 4), and the companion app has shipped only its read-only layer in CI, not to TestFlight (Phase 5). Requirements FR-007, FR-008, FR-010, FR-013, FR-014, and FR-015 are reserved for that work. The full plan is in [[Roadmap]], and the open items are in `TODO.md` and `docs/MVP_BACKLOG.md` in the repository.

## How this wiki is maintained

The pages live in `wiki/` in the repository and are published to the GitHub wiki by CI on merge. A test (`tests/test_wiki.py`) and the constitution's link checker fail the build if a page is unlisted, a link dangles, or a scaffold placeholder survives. If something here disagrees with a document in `docs/`, the document wins; open an issue and the wiki gets corrected.

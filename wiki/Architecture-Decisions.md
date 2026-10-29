# Architecture Decisions

Every significant architecture or safety decision is a numbered ADR in `docs/adr/` in the repository, indexed in `docs/adr/README.md`. Numbers are never reused. A Proposed ADR carries promotion criteria and a named gate, the person who decides when it becomes Accepted. This page gives one paragraph per decision; the ADRs hold the full context and alternatives.

A change to the safety boundary (ADR-0004) needs a new ADR, a hazard review in `docs/SAFETY.md`, and the agreement of the person whose data it shows. See [[Safety]].

## ADR-0001: Record Architecture Decisions

**Accepted, 2026-10-17.** Decisions about where the safety boundary sits need to survive memory and be reviewable by the person with diabetes and anyone who joins later, so every significant decision is a numbered ADR. Changing the boundary then requires a new ADR, which forces the conversation before code exists.

## ADR-0002: Trio on the Primary iPhone Is the Dosing Controller

**Proposed, 2026-10-17. Gate: the person with diabetes, with their endocrinologist's agreement; Eric confirms the logged evidence.** Trio, built from source on the primary iPhone, is the only component that makes dosing decisions. The Dexcom G7 app stays installed as the sensor radio, since Trio reads G7 data from it on the same phone. The official Omnipod 5 app stays available as a fallback. Promotion needs the endocrinologist's review, two weeks of open loop, and five pod changes without unresolved faults. Deferred alternatives: AndroidAPS, Loop, DASH pods, and FreeStyle Libre 3 Plus.

## ADR-0003: Self-Hosted Nightscout Is the Data Hub

**Proposed, 2026-10-17. Gate: Eric.** Every display needs one source of glucose data that is not the phone itself. Nightscout is the community standard and Trio uploads to it natively, so the project runs its own instance, and all code here reads from it with a readable-role token. Promotion needs HTTPS, a strong `API_SECRET`, authentication defaulted to deny, Trio uploading, a working readable token, and one tested restore. See [[Nightscout and Trio Setup]].

## ADR-0004: No Insulin Delivery Code or Hardware in This Repository

**Accepted, 2026-10-17.** A fault in software or hardware that controls insulin delivery can kill someone. Community dosing apps have years of peer review and many users; a two-person repository does not. So this repository contains no code that commands a pump, calculates a dose, or changes therapy settings, no pump hardware designs, and no direct sensor communication. Dosing contributions go upstream to Trio.

## ADR-0005: Read-Only Display Layer in Python, Standard Library at Runtime

**Accepted, 2026-10-17.** Pi e-paper HATs have mature Python drivers and Home Assistant is Python-based, so the display layer is a Python 3.11+ package with three layers (pure domain, application, infrastructure) and only the standard library at runtime. No third-party code sits in the data path, and the safety rules are testable with plain data and a fixed clock. See [[How It Works]].

## ADR-0006: Xteink ESP32-C3 Pocket Display, Kept in Lockstep with Python by Shared Vectors

**Proposed, 2026-10-17. Gate: Eric runs the validation; the person with diabetes decides whether to rely on the device.** Xteink X4 and X3 readers use an ESP32-C3 and have an open source community firmware (CrossPoint), so custom firmware is realistic. A second implementation risks drift, so the rules are ported to dependency-free C++17 with host tests under sanitizers, and `spec/display_vectors.json` becomes the single source of truth every suite must pass, with any rule change updating a vector in the same commit. Promotion needs a flashable device, a device build that renders every vector correctly and survives a 24-hour soak, and one sensor session beside the primary app with no mismatch, freeze, or missed STALE. Since 2026-10-28 the pixels are shared too: `spec/panel_vectors.json` pins every vector's panel, the C++ rasterizer matches it, and a build-only PlatformIO skeleton prints the NO DATA panel over USB serial. See [[Firmware]].

## ADR-0007: C++ Style, Google Base with Naming That Mirrors the Python

**Accepted, 2026-10-24 (proposed 2026-10-18).** The constitution points C++ at the Google style guide, but the firmware rules are a line-for-line port of the Python and reviewers compare them side by side. So the firmware uses clang-format on `BasedOnStyle: Google`, enforced by `make -C firmware/xteink format-check` and a pre-commit hook, with three deviations: snake_case functions and CamelCase enum values mirroring the Python, a 100-column limit to match the Python side's 99, and `#pragma once`.

## ADR-0008: Companion App, with Bolus Requests Only Through Trio's Remote Protocol

**Proposed, 2026-10-18. Gate: the person with diabetes decides; Eric runs the hazard review.** The person with diabetes wants an app that shows glucose clearly and lets them enter a manual bolus, without this project writing insulin delivery software. The app has two layers: a read-only layer first, then a gated bolus request layer that sends a request to Trio over Trio's remote protocol, where Trio applies Max Bolus, Max IOB, a 10-minute duplicate guard, and command expiry. The app never talks to the pod or sensor and never marks anything delivered on its own authority. Promotion needs a hazard analysis with tested mitigations, a fake Trio endpoint, two weeks of the read-only layer on TestFlight, and the agreement of the person with diabetes with their care team informed. See [[Companion App]].

## ADR-0009: Send the Nightscout Readable Token in a Header, Not the URL

**Accepted and implemented, 2026-10-25. Still to do: the check against a real Nightscout.** The displays used to pass their readable token as `?token=`, so it could land in proxy and hosting logs. Nightscout's v1 API, at v15.0.9, also accepts an access token in the `api-secret` request header, which keeps the token out of every URL with one header change per client and no expiry to manage. Exchanging the token for an 8-hour JWT still puts it in a URL path at each exchange and adds refresh state to every client, including the ESP32. Moving to the v3 API adds a rewrite on top of that for no display benefit. JWT bearer auth is the fallback if Nightscout drops the header path.

## ADR-0010: Publish to Home Assistant over MQTT Discovery

**Accepted and implemented, 2026-10-26, with HAZ-013.** Home Assistant's own Nightscout integration exposes the raw last reading with no notion of staleness, so an automation on it can fire on an old number. Lightkeeper would publish its level (STALE before any range check) over MQTT discovery, with a Last Will and `expire_after` so the entity goes `unavailable` the moment the publisher dies instead of freezing on a fresh-looking level. The MQTT client would be a small standard-library publisher (ADR-0005). Pushing to Home Assistant's REST API was rejected because a stopped publisher leaves the last state looking current and the device would hold a full-rights token. Polling a Lightkeeper endpoint was rejected because it serves health data on an open LAN port. Changed since 0.2.0 (not yet released): a fourth sensor (Last reading), the level as an enum of the seven levels, a device name that includes a non-default node id, and status payload version 2, which never carries a negative age (pending Eric's decision).

## ADR-0011: Screen Text v2: No Arrow on STALE, the Failing Link Named, and a STALE Age No Fresh Screen Shows

**Proposed, 2026-10-27. Gate: Eric runs the hazard review (HAZ-017 to HAZ-019); the person with diabetes picks the STALE age wording; both sign the ADR-0011 section of `docs/SAFETY_REVIEW.md`.** Three lines in today's shared vectors say more than the data supports: a STALE screen keeps its trend arrow (`last: 45 mg/dL v` reads as still falling), NO DATA says `Check sensor and phone` above `Nightscout unreachable` when it is the display that cannot reach Nightscout, and a reading 15 minutes and 1 second old shows `15 min ago` under STALE, the same age a fresh screen shows. The ADR proposes one `spec_version` 2 bump: no arrow on a STALE `last:` line, `Check Nightscout/Wi-Fi` on NO DATA after a failed fetch, and a STALE age rounded up (`16 min ago`) or stated as `over 15 min ago`. Those lines are proposals only. Nothing in the ADR is implemented; every screen keeps today's text until the review is signed.

## Reading the statuses together

Six ADRs are Accepted and define the project's shape: 0001, 0004, 0005, 0007, 0009, and 0010. The other five are Proposed for checkable reasons: a therapy decision (0002), infrastructure not yet deployed (0003), hardware not on the bench (0006), an incomplete hazard analysis (0008), and a screen-text change waiting for its hazard review and sign-off (0011). [[Roadmap]] maps them onto the phases.

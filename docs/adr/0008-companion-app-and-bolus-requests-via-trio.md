# ADR-0008: Companion App, with Bolus Requests Only Through Trio's Remote Protocol

Status: Proposed

Date: 2026-10-18

## Relationships

- Extends: ADR-0004, ADR-0005
- Supersedes: none (refines ADR-0004's wording, see Decision)
- Related: docs/SAFETY.md, docs/ROADMAP.md, https://triodocs.org/configuration/settings/features/remote-control/

## Promotion Criteria

- A hazard analysis for the bolus request screen is added to `docs/SAFETY.md` (wrong amount, double send, pending state, rejection handling, stale display at the moment of request) and each hazard has a mitigation with a test.
- The remote protocol is understood from a primary source (LoopFollow's open source implementation and TrioDocs), and a fake Trio endpoint exists for automated tests.
- The read-only part of the app (glucose, trend, age, IOB, recent treatments) has shipped to TestFlight and been used for at least two weeks before the bolus screen is enabled.
- Kaitlin agrees to the design, and her care team knows the app can request boluses.
- Gate: Kaitlin decides; Eric runs the hazard review.

## Context

Kaitlin wants an app of her own that shows her glucose and trends clearly and lets her enter a manual bolus, without us writing insulin-delivery software. Two facts shape the design:

1. An Omnipod 5 pod pairs with one controller. While Trio owns the pod, no other app can command it. Sending a bolus directly would mean our app becoming the pump controller, which is exactly what ADR-0004 rules out.
2. Trio has a Remote Control feature. Another app sends a command over Apple Push Notifications, signed with a shared secret; Trio receives it on the phone, runs its own checks, and accepts or rejects. Trio enforces Max Bolus and Max IOB, rejects a bolus if one over 20% of the requested size was delivered in the last 10 minutes, and drops commands older than 10 minutes or timestamped in the future. Remote boluses also require the feature to be switched on in Trio. The documented client today is LoopFollow.

## Decision

Build a Lightkeeper companion iOS app in two layers:

- **Read-only layer first.** Current glucose, trend, age, insulin on board, recent treatments, and Lightkeeper's own staleness rules, reading from Nightscout exactly as the displays do. Watch complication and widgets. This layer is covered by ADR-0004 as it stands.
- **Bolus request layer, later and gated.** A bolus screen that composes a request and sends it to Trio over Trio's remote protocol. The app never talks to the pod or the sensor. Trio alone decides whether insulin moves. The app shows a request as "pending" until Trio answers, shows rejections with Trio's reason, and never displays anything as delivered on its own authority.

ADR-0004's rule becomes, precisely: *no code in this repository commands a pump, talks to a sensor, or calculates a dose; dosing requests may only be expressed through an established community controller's own remote protocol, which applies that controller's safety limits.*

Amended 2026-10-28: a read-only Android companion app (`apps/android`, FR-020) now exists beside the iOS read-only layer, built on the firmware's C++ rules through JNI and shipped only as a sideloaded debug APK. It has no bolus layer.

## Consequences

- Kaitlin gets the app she asked for, and dosing safety still rests on Trio's reviewed code and limits, not ours.
- The app's bolus path is testable against a fake Trio, and every rejection path can be exercised without insulin.
- We take on a new class of hazard (a human-entered dose request) that needs its own analysis, confirmation design, and clear pending/rejected states.
- We depend on an informally documented protocol; we read LoopFollow's implementation and keep a conformance test so a Trio change breaks a test, not a bolus.
- iOS builds need the paid Apple Developer account (already in place) and a CI build path, since there is no Mac; a cross-platform toolkit is an option if it supports push and widgets well enough.

## Alternatives Considered

- **Our app becomes the pump controller:** rejected; it is insulin delivery software with a user base of one.
- **Carbs and bolus via Nightscout Careportal:** Nightscout's Careportal path carries carbs and temp targets but not boluses, so it cannot do the job.
- **No bolus screen at all, use Trio for every bolus:** the safe default and the fallback if the hazard review does not close. The read-only layer ships regardless.

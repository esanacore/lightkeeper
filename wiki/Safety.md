# Safety

Lightkeeper touches a real person's diabetes care, so its limits are written down, reviewed, and enforced by tests. The source is `docs/SAFETY.md` in the repository, a lightweight hazard analysis in the spirit of ISO 14971, not a regulatory submission.

## Intended use and classification

Lightkeeper displays glucose values already published to Nightscout, for awareness only, for a person with type 1 diabetes and the people around them who already run a CGM and its official app. It is not intended to diagnose, to alarm, or to inform a treatment decision: the primary CGM app and its alarms remain the sole source for action, and every screen is documented to mean "confirm on the primary device."

No Lightkeeper output drives therapy, and no code here communicates with a pump or a sensor. The worst-case failure of the software alone is a wrong or missing number on a secondary screen that always carries an instruction to confirm on the primary device, so the project treats itself as the equivalent of IEC 62304 Class A. It is not submitted, registered, or marketed as a medical device. If a future feature changes that reasoning (an alarm, or the bolus request path in ADR-0008), the classification is re-evaluated first.

Limitations a user must know:

- Wi-Fi and Nightscout dependent: no network, no new numbers.
- Latency: the CGM reports every 5 minutes and the uploader adds delay.
- Staleness: after 15 minutes without a new reading (configurable) the screen says STALE - DO NOT TRUST; it does not guess.
- No alarms: Lightkeeper never sounds, vibrates, or pushes a notification.
- mg/dL only for now (mmol/L is reserved requirement FR-013).
- Thresholds change only which word the display shows. They do not affect dosing or the primary app's alarms. Match them to the alert settings already in the primary app.

## The boundary

1. **No insulin delivery code lives here.** Never a pump command, a dose calculation, or a therapy setting. Dosing is Trio's job. The one planned exception is gated: the companion app may *request* a bolus through Trio's own remote protocol, where Trio decides (ADR-0008; see [[Companion App]]).
2. **No custom insulin delivery hardware.**
3. **No sensor communication.** The sensor stays paired to the Dexcom G7 app and Trio on the primary iPhone.
4. **Read-only, secondary displays only.**
5. **Therapy settings belong to the person with diabetes and their care team**, not to code review.

Crossing this boundary needs a new ADR, a hazard review, and the agreement of the person whose data it shows ([[Architecture Decisions]]).

## The hazard log

Severity and pre-mitigation likelihood in parentheses.

| ID | Hazard | Mitigation | Verified by |
| --- | --- | --- | --- |
| HAZ-001 | Old number shown as current (Critical, Likely) | Staleness checked before any range check | FR-003, `test_fr003_staleness_beats_urgent_low` |
| HAZ-002 | Silent freeze on network failure (Critical, Possible) | Fetch failures degrade to NO DATA or age the last value into STALE; 10 s timeout | FR-005 tests |
| HAZ-003 | Wrong number from a malformed entry (Serious, Possible) | Only `sgv`, whole numbers 39 to 401, valid timestamp; dropped, never repaired | FR-001 tests |
| HAZ-004 | Future-dated reading shown as fresh (Serious, Possible) | More than 2 minutes ahead is STALE | FR-003, `test_fr003_future_dated_reading_is_stale` |
| HAZ-005 | Sentinel shown as a precise number (Serious, Likely) | 39 and 401 render as "LOW (<40)" and "HIGH (>400)" | FR-004, `test_fr004_sentinels_render_as_words_not_numbers` |
| HAZ-006 | Misconfigured thresholds hide a low (Serious, Possible) | Validated at startup; invalid configuration stops the program | NFR-002 tests |
| HAZ-007 | Health data or credentials exposed (Moderate, Possible) | HTTPS required; read-only token; token redacted from errors | NFR-001 tests |
| HAZ-008 | Secondary display trusted over the primary app (Serious, Possible) | Disclaimer in CLI help, README, and device label; STALE and NO DATA say to confirm; iOS strikes through a STALE number | FR-004, manual review |
| HAZ-009 | Trio misconfiguration (Critical, Possible) | Outside this codebase: open loop first, settings validated with the endocrinologist | Process, `docs/SETUP.md` |
| HAZ-010 | Bolus request wrong or doubled (Critical, Possible, planned) | Request-only: Trio enforces its limits; app requires confirm, shows pending, never marks delivered, disabled when STALE | ADR-0008 criteria; tests not yet written |
| HAZ-011 | One bad entry or failed write blanks the display for a long time (Critical, Possible) | Numbers range-checked before conversion, timestamps bounded to 2000-2100, one poisoned entry never discards its neighbors; watch loop survives a failed SVG write; SVG carries a "written" stamp | FR-001, `test_haz011_*`, vector `huge_value_rejected` |
| HAZ-012 | iOS app crashes on launch or runs on thresholds other than shown (Serious, Possible) | Swift range-checks before `Int()`; settings edit a draft, Save disabled while invalid, invalid set on disk resets to defaults | FR-012, `testHugeNumbersThrowInsteadOfCrashing` |

HAZ-010 was logged before its feature exists, on purpose. Every screen is pictured in [[Display States]].

## Review triggers

The log is re-reviewed when a change touches parsing, classification, rendering, or the Nightscout client in any implementation; when a display host's clock is found wrong; when a new display device or alert path is added; when the upstream stack changes; and when a real-world incident or near miss happens, which gets a new HAZ ID. [[Contributing]] describes the review in a pull request.

## The disclaimer wording

Every public surface carries one line:

> Lightkeeper is a secondary display and not a medical device. Always confirm on the primary CGM app.

The project never calls anything it does an "alarm" ([[Community Research]]).

Still open: the person with diabetes has not yet reviewed `docs/SAFETY.md` and the default thresholds (55 / 70 / 180 / 250 mg/dL, stale after 15 minutes), a Phase 0 exit item in `docs/MVP_BACKLOG.md`. The review is a one-page checklist, `docs/SAFETY_REVIEW.md`: confirm or change each threshold and the stale limit, acknowledge the limitations, and sign off.

Back to [[Home]], or see [[Security and Privacy]] for the data side of the same question.

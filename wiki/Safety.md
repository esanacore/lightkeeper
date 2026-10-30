# Safety

Lightkeeper touches a real person's diabetes care, so its limits are written down, reviewed, and enforced by tests. The source is `docs/SAFETY.md` in the repository, a lightweight hazard analysis in the spirit of ISO 14971, not a regulatory submission.

## Intended use and classification

Lightkeeper displays glucose values already published to Nightscout, for awareness only, for a person with type 1 diabetes and the people around them who already run a CGM and its official app. It is not intended to diagnose, to alarm, or to inform a treatment decision: the primary CGM app and its alarms remain the sole source for action, and every screen is documented to mean "confirm on the primary device."

No Lightkeeper output drives therapy, and no code here communicates with a pump or a sensor. The worst-case failure of the software alone is a wrong or missing number on a secondary screen that always carries an instruction to confirm on the primary device, so the project treats itself as the equivalent of IEC 62304 Class A. It is not submitted, registered, or marketed as a medical device. If a future feature changes that reasoning (an alarm, or the bolus request path in ADR-0008), the classification is re-evaluated first. The desktop window and the Android app, both added on 2026-10-28, take every status word from the vector lines, add only stamps, captions, key hints, the setup card and the disclaimer, and sound nothing, so the classification is unchanged.

Limitations a user must know:

- Wi-Fi and Nightscout dependent: no network, no new numbers.
- Latency: the CGM reports every 5 minutes and the uploader adds delay.
- Staleness: after 15 minutes without a new reading (configurable) the screen says STALE - DO NOT TRUST; it does not guess.
- No alarms: Lightkeeper never sounds, vibrates, or pushes a notification.
- mg/dL only for now (mmol/L is reserved requirement FR-013).
- Thresholds change only which word the display shows. They do not affect dosing or the primary app's alarms. Match them to the alert settings already in the primary app.

## The boundary

1. **No insulin delivery code lives here.** Never a pump command, a dose calculation, or a therapy setting. Dosing is Trio's job. The one planned exception is gated: the iOS companion app may *request* a bolus through Trio's own remote protocol, where Trio decides (ADR-0008; see [[Companion App]]).
2. **No custom insulin delivery hardware.**
3. **No sensor communication.** The sensor stays paired to the Dexcom G7 app and Trio on the primary iPhone.
4. **Read-only, secondary displays only.**
5. **Therapy settings belong to the person with diabetes and their care team**, not to code review.

Crossing this boundary needs a new ADR, a hazard review, and the agreement of the person whose data it shows ([[Architecture Decisions]]).

## The hazard log

Severity and pre-mitigation likelihood in parentheses.

| ID | Hazard | Mitigation | Verified by |
| --- | --- | --- | --- |
| HAZ-001 | Old number shown as current (Critical, Likely) | Staleness checked before any range check; the desktop window and the Android app re-age on their own timers | FR-003, `test_fr003_staleness_beats_urgent_low`, `test_fr018_reading_turns_stale_without_a_fetch` |
| HAZ-002 | Silent freeze on network failure (Critical, Possible) | Fetch failures degrade to NO DATA or age the last value into STALE; 10 s timeout; the desktop window's two-interval watchdog, retry on a new worker and monotonic ticker; the Android app's 20-second fetch limit | FR-005 tests, `test_fr018_hung_fetch_becomes_unreachable_then_stale` |
| HAZ-003 | Wrong number from a malformed entry (Serious, Possible) | Only `sgv`, whole numbers 39 to 401, valid timestamp; dropped, never repaired | FR-001 tests |
| HAZ-004 | Future-dated reading shown as fresh (Serious, Possible) | More than 2 minutes ahead is STALE | FR-003, `test_fr003_future_dated_reading_is_stale` |
| HAZ-005 | Sentinel shown as a precise number (Serious, Likely) | 39 and 401 render as "LOW (<40)" and "HIGH (>400)" | FR-004, `test_fr004_sentinels_render_as_words_not_numbers` |
| HAZ-006 | Misconfigured thresholds hide a low (Serious, Possible) | Validated at startup; invalid configuration stops the program | NFR-002 tests |
| HAZ-007 | Health data or credentials exposed (Moderate, Possible) | HTTPS required; read-only token; token redacted from errors | NFR-001 tests |
| HAZ-008 | Secondary display trusted over the primary app (Serious, Possible) | Disclaimer in CLI help, README, and device label; STALE and NO DATA say to confirm; on STALE the iOS and Android apps show no large number; the old value is only in the struck `last:` line | FR-004, manual review |
| HAZ-009 | Trio misconfiguration (Critical, Possible) | Outside this codebase: open loop first, settings validated with the endocrinologist | Process, `docs/SETUP.md` |
| HAZ-010 | Bolus request wrong or doubled (Critical, Possible, planned) | Request-only: Trio enforces its limits; app requires confirm, shows pending, never marks delivered, disabled when STALE | ADR-0008 criteria; tests not yet written |
| HAZ-011 | One bad entry or failed write blanks the display for a long time (Critical, Possible) | Numbers range-checked before conversion, timestamps bounded to 2000-2100, one poisoned entry never discards its neighbors; watch loop survives a failed SVG write; SVG carries a "written" stamp; PNG and BMP images carry a local `HH:MM` stamp | FR-001, `test_haz011_*`, vector `huge_value_rejected` |
| HAZ-012 | A companion app runs on thresholds other than shown, or the iOS app crashes on launch (Serious, Possible) | Swift range-checks before `Int()`; settings edit a draft, Save disabled while invalid, invalid set on disk resets to defaults; the Android app resets an invalid set on disk and writes it back | FR-012, `testHugeNumbersThrowInsteadOfCrashing`, `testAnInvalidStoredSetIsResetAndWrittenBackToDisk` |
| HAZ-013 | A Home Assistant automation acts on a level that is no longer true (Serious, Possible) | The displays' own classification; Last Will and `expire_after`; state never retained; no number for STALE, NO DATA or sentinels; never a negative age | FR-008, `tests/test_home_assistant.py` |
| HAZ-014 | An image or panel that stopped updating looks current (Critical, Possible) | A local `HH:MM` stamp of when the image was drawn, never the reading's time; always on for exported PNG and BMP; the desktop window stamps every redraw, in its text view too | FR-006, `test_haz014_png_and_bmp_written_atomically_with_stamp`, `test_fr018_stamp_is_drawn_on_the_bitmap` |
| HAZ-015 | A widget keeps a fresh-looking frame long after the data went stale (Critical, Possible once widgets ship) | The glance timeline schedules STALE in advance | FR-019, `testFR019EntryAtFirstStaleMillisecond` |
| HAZ-016 | A port draws a different panel from the reference (Serious, Possible) | Integer-only layout and pixel vectors every renderer must match | FR-016, `test_fr016_every_panel_vector_matches_python` |

HAZ-014 to HAZ-016 wait for the hazard review with the person with diabetes. HAZ-017 to HAZ-019 are reserved for ADR-0011, which is Proposed.

HAZ-010 was logged before its feature exists, on purpose. Every screen is pictured in [[Display States]].

## Review triggers

The log is re-reviewed when a change touches parsing, classification, rendering, or the Nightscout client in any implementation; when a display host's clock is found wrong; when a new display device or alert path is added; when the upstream stack changes; and when a real-world incident or near miss happens, which gets a new HAZ ID. A change to the panel layout or any panel renderer is a trigger too. So is any new surface that shows or speaks the vector lines, after the calm-technology checklist in `docs/BRAND.md`; building the widget, StandBy or Live Activity extension (HAZ-015); the device firmware gaining networking, a clock or a panel driver, or the Pi panel driver landing (HAZ-014, HAZ-016); and Eric deciding a pending choice a mitigation rests on, such as the stamp default on physical panels or the status payload version. Two display devices were added on 2026-10-28, the desktop window and the Android app: each needs the hazard review and the sign-off in `docs/SAFETY_REVIEW.md` before anyone relies on it, and any change to either is a trigger. Every test the hazard log cites is checked by `tests/test_safety_doc.py`. [[Contributing]] describes the review in a pull request.

## The disclaimer wording

Every public surface carries one line:

> Lightkeeper is a secondary display and not a medical device. Always confirm on the primary CGM app.

The project never calls anything it does an "alarm" ([[Community Research]]).

Still open: the person with diabetes has not yet reviewed `docs/SAFETY.md` and the default thresholds (55 / 70 / 180 / 250 mg/dL, stale after 15 minutes), a Phase 0 exit item in `docs/MVP_BACKLOG.md`. The review is a one-page checklist, `docs/SAFETY_REVIEW.md`: confirm or change each threshold and the stale limit, acknowledge the limitations, and sign off. The ADR-0011 section of that sheet is still to be signed too, and the two new surfaces, the desktop window and the Android app, wait for the same review.

Back to [[Home]], or see [[Security and Privacy]] for the data side of the same question.

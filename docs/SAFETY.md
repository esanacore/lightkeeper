# Safety Boundary and Hazard Analysis

This project touches type 1 diabetes care for a real person. This document sets the hard boundary for what the repository may do, and records the hazards we have thought about. It is a lightweight analysis in the spirit of ISO 14971, not a regulatory submission, and nothing here is a medical device.

## The Boundary

1. **No insulin delivery code lives here.** This repository never sends commands to a pump, never calculates a dose, and never changes therapy settings. Dosing is done only by Trio, an established community project with its own review and testing culture. Improvements to dosing go upstream to Trio, through its process, not into this repo. The one planned exception is narrow and gated: the companion app may *request* a bolus through Trio's own remote protocol, where Trio applies its limits and decides (ADR-0008, not yet accepted).
2. **No custom insulin delivery hardware.** We do not build pumps, pump controllers, or radio bridges that talk to pumps.
3. **No sensor communication.** We do not talk to the Dexcom G7 directly. The sensor stays paired to the Dexcom G7 app and Trio on Kaitlin's iPhone.
4. **Read-only, secondary displays only.** Everything we build reads from Nightscout and shows data. Every display says, or is documented to mean, "confirm on the primary device."
5. **Therapy settings belong to Kaitlin and her care team.** Basal rates, carb ratios, sensitivity factors, and targets are decided with her endocrinologist, not in code review.

A change that would cross this boundary needs a new ADR, a hazard review, and Kaitlin's explicit agreement before any code is written.

## Hazard Log

Severity: how bad the outcome could be. Likelihood: before mitigation. Each mitigation names the requirement or test that verifies it.

| ID | Hazard | Cause | Severity | Likelihood | Mitigation | Verified by |
| --- | --- | --- | --- | --- | --- | --- |
| HAZ-001 | Display shows an old number as if current, masking a real low | Nightscout or uploader stopped, display keeps last value | Critical | Likely | Staleness is checked before any range check; old data shows STALE - DO NOT TRUST | FR-003, `test_fr003_staleness_beats_urgent_low` |
| HAZ-002 | Display freezes silently when the network fails | Unhandled exception or hung request | Critical | Possible | Every fetch failure degrades to NO DATA or ages the last good value into STALE; request timeout of 10 seconds | FR-005, `test_fr005_fetch_error_reuses_last_good_and_ages_it_into_stale` |
| HAZ-003 | Wrong number shown from a malformed entry | Bad upload, non-sensor entry, unit mix-up | Serious | Possible | Strict parsing: only `sgv` entries, whole numbers, 39 to 401 mg/dL, valid timestamp; bad entries are dropped, never repaired | FR-001, `test_fr001_rejects_untrustworthy_entries` |
| HAZ-004 | Future-dated reading displayed as fresh | Wrong clock on phone, server, or display | Serious | Possible | Readings more than 2 minutes in the future are STALE | FR-003, `test_fr003_future_dated_reading_is_stale` |
| HAZ-005 | Out-of-range sensor value shown as a precise number | Sensor reports LOW/HIGH sentinels (39/401) | Serious | Likely | Sentinels render as "LOW (<40)" and "HIGH (>400)" | FR-004, `test_fr004_sentinels_render_as_words_not_numbers` |
| HAZ-006 | Misconfigured thresholds hide a low | Typo in env vars, inverted ranges | Serious | Possible | Thresholds validated at startup, invalid config stops the program | NFR-002, `test_nfr002_invalid_thresholds_are_rejected` |
| HAZ-007 | Health data or Nightscout credentials exposed | Plain HTTP, token in logs or errors | Moderate | Possible | HTTPS required; read-only token only; token redacted from all errors | NFR-001, `test_nfr001_network_errors_redact_the_token` |
| HAZ-008 | Someone trusts the secondary display over the primary app | Display looks authoritative | Serious | Possible | Disclaimer in CLI help and README; STALE and NO DATA states tell the user to confirm on the primary device | FR-004, manual review |
| HAZ-010 | Companion app bolus request delivers the wrong amount or delivers twice (planned feature) | Typo, double tap, retry after timeout, stale glucose shown at request time | Critical | Possible | Request-only design: Trio enforces max bolus, max IOB, and a 10-minute duplicate guard and rejects stale or future-dated requests; app requires an explicit confirm step, shows a pending state until Trio answers, never marks anything delivered on its own, and disables the screen when its own glucose display is STALE | ADR-0008 promotion criteria; tests against a fake Trio (not yet written) |
| HAZ-009 | Trio misconfiguration causes over or under delivery | Wrong therapy settings, pump driver bug (Omnipod 5 support is new, released September 2026) | Critical | Possible | Outside this codebase. Open loop first, closed loop only after settings are validated with her endo; keep the official Omnipod 5 app as fallback; report bugs upstream with logs | Process, see `docs/SETUP.md` phases |

## Review Triggers

Re-review this log when:

- any change touches parsing, classification, rendering, or the Nightscout client;
- a new display device or alert path is added;
- the upstream stack changes (new Trio release, Nightscout major version, sensor or pump change);
- a real-world incident or near miss happens. Record it here with a new HAZ ID.

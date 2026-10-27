# ADR-0011: Screen Text v2: No Arrow on STALE, the Failing Link Named, and a STALE Age No Fresh Screen Shows

Status: Proposed

Date: 2026-10-27

## Relationships

- Extends: ADR-0006 (one set of shared vectors keeps every implementation in lockstep)
- Supersedes: none
- Related: FR-003, FR-004, FR-009, FR-012, FR-017 (the spoken form, `spec/spoken_vectors.json`), HAZ-001, HAZ-008, docs/SAFETY_REVIEW.md, decisions D5, D6, D7 and D8; deferred FR-013, FR-014 and FR-015

## Promotion Criteria

Nothing in this ADR is implemented while it is Proposed (decision D6). Until every criterion below is met, `spec/display_vectors.json` stays at `spec_version` 1 and every screen line stays byte-identical.

- Hazard review: HAZ-017, HAZ-018 and HAZ-019 (below) are added to the hazard log in `docs/SAFETY.md`, each with its mitigation and the tests that verify it, and the classification rationale is re-read. Gate: Eric.
- Kaitlin chooses the STALE age wording for change (c): round up (c1) or "over N min ago" (c2). Gate: Kaitlin.
- Eric and Kaitlin sign the ADR-0011 section of `docs/SAFETY_REVIEW.md` (the text to add is under Sign-off). Gate: Eric and Kaitlin.
- One pull request makes every change listed under "What Must Change", bumps `spec_version` to 2, and passes the Python suite at 100% line and branch coverage, the firmware host tests under ASan and UBSan, and all three Swift jobs in `.github/workflows/ios.yml`. Gate: CI, then Eric's review.

## Context

`spec/display_vectors.json` fixes, character for character, what every Lightkeeper screen says: the Python tool, the ESP32 firmware, the iOS app, the e-paper gallery, the demo page, and the Home Assistant `lines` attribute. Staleness is decided before any range check, and nothing here changes that. But three lines in `spec_version` 1 say more than the data supports, or point the wrong way:

- (a) **A STALE screen keeps the trend arrow.** `last: 45 mg/dL v` on a reading that is 40 minutes old reads as "still falling", and a stale `^` reads as "on its way up, no need to check". An arrow is a claim about now, and a STALE screen has nothing to say about now. The spoken form (FR-017) already leaves the trend out of STALE sentences, so today the screen and the speech differ on exactly this point.
- (b) **NO DATA points at two places at once.** When the display cannot reach Nightscout and has no earlier reading, the screen says `Check sensor and phone` directly above `Nightscout unreachable`. The sensor and the phone may be fine; the link that failed is the display's Wi-Fi or the Nightscout site.
- (c) **The same age appears on both sides of the cutoff.** Ages are whole minutes, rounded down, so a reading 15 minutes old shows `IN RANGE` and `15 min ago`, while one 15 minutes and 1 second old shows `STALE - DO NOT TRUST` and also `15 min ago`. Someone learning "STALE after 15 minutes" sees the rule contradict itself, which teaches them to discount STALE.

Each change rewrites an existing vector, so each needs a `spec_version` bump, and each bump means Python, C++ and Swift (and every generated file) change together. One bump for all three is one coordinated change instead of three.

None of the three touches a fresh screen. Every screen before the stale cutoff keeps its exact text.

## Decision (Proposed)

Bundle (a), (b) and (c) into `spec_version` 2. The lines below are the complete set of vector changes: 9 of the 39 vectors change, and the other 30 stay byte-identical.

### (a) No trend arrow on a STALE "last:" line: proposed HAZ-017

Rule: on a STALE screen, line 2 is `last: ` followed by the number and its unit, with no arrow. Sensor sentinels already carry no arrow and keep their words (`last: LOW (<40)`, `last: HIGH (>400)`). Fresh screens keep the arrow.

| Vector | Line | Before (`spec_version` 1) | After (`spec_version` 2) |
| --- | --- | --- | --- |
| `stale_at_16_minutes` | 2 | `last: 120 mg/dL ->` | `last: 120 mg/dL` |
| `stale_beats_urgent_low` | 2 | `last: 45 mg/dL v` | `last: 45 mg/dL` |
| `future_dated` | 2 | `last: 120 mg/dL ->` | `last: 120 mg/dL` |
| `stale_while_unreachable_stays_four_lines` | 2 | `last: 120 mg/dL ->` | `last: 120 mg/dL` |
| `stale_at_15_minutes_1_second` | 2 | `last: 120 mg/dL ->` | `last: 120 mg/dL` |
| `future_skew_2_minutes_1_second_stale` | 2 | `last: 120 mg/dL ->` | `last: 120 mg/dL` |
| `rejected_newest_does_not_freshen_older` | 2 | `last: 110 mg/dL ->` | `last: 110 mg/dL` |
| `custom_stale_after_10_minutes` | 2 | `last: 120 mg/dL ->` | `last: 120 mg/dL` |

Spoken form: no change. STALE sentences already say no trend word.

Proposed HAZ-017:

| Hazard | Cause | Severity | Likelihood | Mitigation | Verified by |
| --- | --- | --- | --- | --- | --- |
| A STALE screen's trend arrow is read as the current direction | The `last:` line keeps the arrow of a reading that may be hours old, so `last: 45 mg/dL v` reads as "still falling" and a stale `^` as "coming up" | Serious | Possible | STALE value lines carry no arrow in any implementation; the spoken STALE form says no trend word (FR-017) | The 8 vectors above at `spec_version` 2 in all three suites, plus a test in each that, for every trend, no STALE line contains an arrow token (to be written with the change) |

### (b) NO DATA names the failing link: proposed HAZ-018

Rule: when the latest fetch failed and the screen is NO DATA (no earlier reading to age), line 2 reads `Check Nightscout/Wi-Fi`. When Nightscout answered but sent nothing trustworthy (no fetch error), line 2 stays `Check sensor and phone`, which is still the right advice. Lines 1, 3 and 4 do not change.

| Vector | Line | Before (`spec_version` 1) | After (`spec_version` 2) |
| --- | --- | --- | --- |
| `no_data_unreachable` | 2 | `Check sensor and phone` | `Check Nightscout/Wi-Fi` |

The full screen after the change: `NO DATA`, `Check Nightscout/Wi-Fi`, `Confirm on primary device`, `Nightscout unreachable`. The other NO DATA vectors (`no_data`, `invalid_value_rejected`, `non_sgv_rejected`, `huge_value_rejected`, `all_entries_rejected_is_no_data`) have no fetch error and do not change.

Spoken form, `no_data_unreachable`:

- Before: `No data. Check sensor and phone. Confirm on the primary device. Nightscout unreachable.`
- After: `No data. Check Nightscout and Wi-Fi. Confirm on the primary device. Nightscout unreachable.`

Proposed HAZ-018:

| Hazard | Cause | Severity | Likelihood | Mitigation | Verified by |
| --- | --- | --- | --- | --- | --- |
| NO DATA sends the household to the wrong place, so an outage lasts longer | `Check sensor and phone` sits above `Nightscout unreachable` when it is the display that cannot reach Nightscout, so someone checks a working sensor and phone instead of the display's Wi-Fi or the Nightscout site | Moderate | Possible | With a fetch error, NO DATA line 2 names the failing link; without one, it keeps pointing at the sensor and phone | Vector `no_data_unreachable` at `spec_version` 2 in all three suites, plus a test in each that the two NO DATA forms differ only in line 2 and only by the fetch error (to be written with the change) |

### (c) A STALE age never equals a fresh one: proposed HAZ-019

Kaitlin chooses one of two wordings. Both keep fresh ages exactly as they are (whole minutes, rounded down) and both change only what a STALE screen says about the reading's age.

- (c1) **Round up.** A STALE age is rounded up to the next whole minute. A STALE reading is always older than the limit, so it always shows at least one minute more than any fresh screen can. Every other STALE vector is a whole number of minutes old and keeps its text.
- (c2) **"over N min ago".** In the first minute past the limit, where the rounded-down age equals the limit N, a STALE screen says `over N min ago`; from the next minute on it says `N min ago` as today. N is the configured stale limit, so with a 10-minute limit it reads `over 10 min ago`. This is the plan's recommendation, because the words state the rule.

| Vector | Line | Before (`spec_version` 1) | After, (c1) round up | After, (c2) "over" |
| --- | --- | --- | --- | --- |
| `stale_at_15_minutes_1_second` | 3 | `15 min ago` | `16 min ago` | `over 15 min ago` |

With (a), this vector's full screen after the change is `STALE - DO NOT TRUST`, `last: 120 mg/dL`, then `16 min ago` (c1) or `over 15 min ago` (c2), then `Confirm on primary device`.

Spoken form, `stale_at_15_minutes_1_second`:

- Before: `Stale, do not trust. Last reading 120 milligrams per deciliter, 15 minutes ago. Confirm on the primary device.`
- After (c1): `Stale, do not trust. Last reading 120 milligrams per deciliter, 16 minutes ago. Confirm on the primary device.`
- After (c2): `Stale, do not trust. Last reading 120 milligrams per deciliter, over 15 minutes ago. Confirm on the primary device.`

What each choice costs:

- (c1) changes only the rounding inside the three render functions and the spoken form (an integer ceiling for a positive age; future-dated ages keep `time is in the future`). The status payload's `age_minutes` stays the rounded-down number, because it is data rather than screen text; whether it follows is for the Home Assistant work (D14) to decide.
- (c2) needs the stale limit where the line is drawn. `render_lines` (Python), `renderLines` (Swift) and `lk::render` (C++), and the two spoken-form functions, gain the limit as a required argument, with no default, so a caller can never silently fall back to 15 minutes. Every caller passes `thresholds.stale_after`.

Proposed HAZ-019:

| Hazard | Cause | Severity | Likelihood | Mitigation | Verified by |
| --- | --- | --- | --- | --- | --- |
| A STALE screen shows an age that a fresh screen also shows, so STALE looks arbitrary and gets discounted | Ages are rounded down, so 15 min 1 s shows `15 min ago` under STALE while 15 min 0 s shows `15 min ago` under IN RANGE | Moderate | Likely (every outage passes through that minute) | A STALE age is always stated as past the limit: rounded up (c1) or `over N min ago` (c2) | Vector `stale_at_15_minutes_1_second` at `spec_version` 2, plus a sweep in each suite over every second from 0 to twice the limit, for the default and a custom limit, asserting that no STALE age line equals any fresh age line (to be written with the change) |

## Width Check

Measured with the reference rasterizer that draws the gallery today (`epaper_bitmap.text_width` and `fit_scale`; margin `max(4, (h*6+50)//100)`). A glyph is 5 pixels wide at scale 1, and the gap between glyphs is `max(1, scale // 2)`.

On the 2.9" panel, 296x128 (margin 8, usable width 280 px), every affected screen draws its body at scale 2, before and after:

| Line | Characters | Width at scale 2 |
| --- | --- | --- |
| `last: 120 mg/dL ->` → `last: 120 mg/dL` | 18 → 15 | 197 → 164 px |
| `last: 45 mg/dL v` → `last: 45 mg/dL` | 16 → 14 | 175 → 153 px |
| `Check sensor and phone` → `Check Nightscout/Wi-Fi` | 22 → 22 | 241 → 241 px |
| `15 min ago` → `16 min ago` (c1) | 10 → 10 | 109 → 109 px |
| `15 min ago` → `over 15 min ago` (c2) | 10 → 15 | 109 → 164 px |
| Widest body line on these screens, unchanged: `Confirm on primary device` | 25 | 274 px |
| On `stale_while_unreachable_stays_four_lines`, unchanged: `Nightscout unreachable` | 22 | 241 px |

On the 1.54" bench board, 200x200 (margin 12, usable width 176 px), every affected screen draws its body at scale 1, before and after. That is today's pinned small-panel exception (D4): `Confirm on primary device` is 149 px at scale 1 and 274 px at scale 2. At scale 1 the changed lines measure 107 → 89 px, 95 → 83 px, 131 → 131 px, 59 → 59 px (c1) and 59 → 89 px (c2).

No line after the change is wider than the widest body line already on its screen, so no scale changes on either panel, and the headlines (`STALE - DO NOT TRUST`, `NO DATA`) do not change at all. Nothing grows either: dropping the arrow could otherwise let a per-line layout draw the shorter `last:` line larger, but the panel layout rule (LK-03) keeps a STALE `last:` line at body scale and never above the age line, so an old value never becomes the hero. The firmware's line buffer (`kLineChars` 32, so 31 characters) holds every new line; the longest is 22 characters, and `over N min ago` stays under 20 for any limit up to 99,999 minutes. Re-run both checks, and the pixel vectors, when the change lands.

## What Must Change

All of this lands in one pull request, after the promotion criteria are met.

- Rules, in all three implementations:
  - `src/lightkeeper/application/monitor.py` (`render_lines`).
  - `apps/ios/LightkeeperCore/Sources/LightkeeperCore/Render.swift` (`renderLines`, and a STALE value text without the arrow).
  - `firmware/xteink/lib/glucose_rules/glucose_rules.cpp` (`render`), and `glucose_rules.h` if (c2) adds the limit argument.
- Vectors: `spec/display_vectors.json`, the 9 vectors above and `spec_version` 2. The three assertions move to 2 together: `EXPECTED_SPEC_VERSION` in `tests/test_vectors.py`, the `spec_version` check in `VectorTests.swift`, and `kExpectedSpecVersion` in `firmware/xteink/test/host/test_glucose_rules.cpp`.
- Spoken form: `src/lightkeeper/application/spoken.py` and `apps/ios/LightkeeperCore/Sources/LightkeeperCore/Spoken.swift` for (b) and (c); `spec/spoken_vectors.json` regenerated with `python tools/gen_spoken_vectors.py`; the literal sentences in `tests/test_spoken.py` and `SpokenVectorTests.swift`.
- Tests that pin today's text: `tests/test_monitor.py` (the STALE `last: 120 mg/dL ->` lines), the new HAZ-017, HAZ-018 and HAZ-019 tests in every suite, and anything a fresh search for the old lines turns up.
- Generated outputs, regenerated by their own tools, never by hand:
  - the gallery, by `python tools/gen_display_gallery.py`: `docs/DISPLAY_STATES.md`, `docs/img/display-states/*.svg` and `docs/img/epaper/*.png` for the 9 vectors;
  - the demo states, the generated block in `demo.html`, by the same tool;
  - the pixel vectors, `spec/panel_vectors.json` (LK-03's `tools/gen_panel_spec.py`), which the web panel (LK-08) and the firmware panel rasterizer (LK-09) also check;
  - the spoken vectors, as above.
- Surfaces that draw the trend outside the vector lines hide it on STALE. Today that is `apps/ios/Lightkeeper/Sources/ContentView.swift`, which shows `trend.symbol` beside a STALE number; `Presentation.swift` (LK-07, in the same batch as this ADR) is specified to give STALE no separate arrow. Check every surface that exists by then (desktop, terminal, widgets, Android, the demo's mock cards).
- Documents: the HAZ-017, HAZ-018 and HAZ-019 rows in `docs/SAFETY.md`; FR-004-AC-2 in `docs/PRODUCT_REQUIREMENTS.md` (no arrow on STALE, the NO DATA wording after a failed fetch, and the STALE age rule); `docs/REQUIREMENTS_TRACEABILITY.md`; `docs/TEST_PLAN.md`; `CHANGELOG.md`; the "NO DATA with Nightscout unreachable" sections of `docs/TROUBLESHOOTING.md` and `wiki/Troubleshooting.md` (the wiki quotes today's four lines), and the cutoff wording in `wiki/Display-States.md`; the signed section of `docs/SAFETY_REVIEW.md`; and this ADR's status in `docs/adr/README.md`.
- Not affected: the classification (`classify` and its thresholds), the status payload's `level` and `mgdl` rules, and every fresh screen. The Home Assistant `lines` attribute follows the vectors on its own.

## Sign-off

The section below is added to `docs/SAFETY_REVIEW.md` when this ADR goes to review. Nothing changes until both lines are signed.

> ### 5. Screen text v2 (ADR-0011)
>
> Three small wording changes. Each one says less than today about old or missing data, and none of them touches a fresh screen.
>
> | Change | Today | Proposed | Agree? |
> | --- | --- | --- | --- |
> | No arrow beside an old number | `last: 45 mg/dL v` | `last: 45 mg/dL` | [ ] yes [ ] no |
> | NO DATA names the link that failed when the display can't reach Nightscout | `Check sensor and phone` | `Check Nightscout/Wi-Fi` | [ ] yes [ ] no |
> | A STALE age never matches a fresh one (15 min 1 s old) | `15 min ago` | [ ] `16 min ago` (round up) [ ] `over 15 min ago` | pick one |
>
> - Kaitlin: ______________________ Date: ____________
> - Eric: ______________________ Date: ____________

## Deferred, with Their Gates

Each of these changes screen text too, but none is part of this bump. Each one is its own vector change across Python, C++ and Swift, plus the gallery, the demo and the pixel and spoken vectors, with its own hazard entry and Kaitlin's sign-off (decision D8).

- **FR-013, mmol/L.** Gate: the household asks for it. One setting switches every implementation, with one shared rounding rule, thresholds entered in the same unit, and vectors in both units; its hazard entry covers unit confusion.
- **FR-014, signed delta.** Gate: the household asks for it. Shown only between two consecutive fresh readings 4 to 7 minutes apart, and never on STALE or NO DATA.
- **FR-015, phone quiet.** Gate: research into Nightscout's `devicestatus`, so that "phone quiet N min" reports the uploader phone reliably. FR-015 is reserved today as device status on hardware displays (battery, and the time since the display itself last reached Nightscout); its wording is settled when it is promoted.
- **The compact field.** Gate: widgets or Live Activities landing. It is an optional field (no `spec_version` bump, but new text in every implementation) and always carries the age or STALE, never a bare number on a STALE compact form.
- **Graded aging.** Gate: decision D7, a hazard review and Kaitlin's agreement. The current recommendation is no cue before the cutoff; the only variant on the table is a style-only cue from 10 to 15 minutes with the text unchanged, because a half-faded number can read as "a bit old but fine".

## Consequences

- A STALE screen no longer suggests a direction, NO DATA after a failed fetch points at the link that failed, and the age on a STALE screen can no longer be mistaken for a fresh one. The screen and the spoken form agree again on STALE (neither gives a trend).
- One coordinated change: three implementations, three version assertions, and every generated file move together, and any port that reads the vectors (web panel, Android) fails loudly until it follows.
- With (c2), the render functions take the stale limit, a signature change in three languages; with (c1) they do not.
- The household sees changed words once. The signed review sheet records that they expected it.
- A Home Assistant automation that matches on line text would need updating; the documented automations match on `level`, which does not change.

## Alternatives Considered

- **Three separate bumps** (`spec_version` 2, 3 and 4). Three rounds of lockstep changes and regenerated files, three reviews for Kaitlin, and three windows in which one implementation can lag. Rejected for one bump.
- **(a) Keep the arrow but strike it or grey it.** That is presentation, and plain-text surfaces (the CLI, the Home Assistant `lines` attribute, screen readers) have no strike. Rejected: the text itself must not claim a direction.
- **(a) Replace the arrow with a word such as `(old trend)`.** Longer, and it still states a trend. Rejected.
- **(b) Name only one link** (`Check Wi-Fi` or `Check Nightscout`). The display cannot tell which one failed, so it names both.
- **(b) Drop line 2 when Nightscout is unreachable.** It would leave NO DATA without a next step. Rejected.
- **(c) Show seconds** (`15 min 1 s ago`). The age would tick every second, which Lightkeeper never does. Rejected.
- **(c) Move the cutoff to whole minutes** (STALE from 16:00). That changes the classification rule (FR-003) itself, the safety core every implementation shares, to fix a wording problem. Rejected.
- **Fold FR-013, FR-014, FR-015 and the compact field into this bump.** It would make one review too large to check line by line (D8). Deferred above.
- **Do nothing.** It keeps three lines that are known to mislead. Rejected, pending the review above.

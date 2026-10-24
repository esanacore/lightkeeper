# Display States

Every screen Lightkeeper can show, drawn at the size of a 2.9 inch e-paper panel (296 by 128 pixels). These images are generated from `spec/display_vectors.json` by `tools/gen_display_gallery.py`, the same 39 cases the Python, C++, and Swift tests run, so the pictures always match real behavior. A test fails if the committed gallery in `docs/DISPLAY_STATES.md` drifts from the generator's output. The images below are served from the repository's `main` branch; `demo.html` shows the same screens with a button for every vector.

Lightkeeper is a secondary display and not a medical device. Always confirm on the primary CGM app before acting.

## The rules behind the pictures

- Anything older than 15 minutes (the default stale limit) or dated more than 2 minutes in the future shows STALE, even when the number would be alarming. Staleness is decided before the value is looked at.
- Sensor out-of-range values (39 and 401 mg/dL, Nightscout's sentinels) show as words, not numbers.
- The screen never uses more than four lines, and every line is plain ASCII.
- Age is shown in whole minutes, floored. Zero minutes shows "just now".
- Trend arrows are plain text: `^^`, `^`, `/`, `->`, `\`, `v`, `vv`, and `?` for an unrecognized direction string.
- The default thresholds are 55 / 70 / 180 / 250 mg/dL. At or below 55 is URGENT LOW, below 70 is LOW, 70 through 180 inclusive is IN RANGE, above 180 is HIGH, at or above 250 is URGENT HIGH. Thresholds change only which word the display shows. They do not affect dosing or the primary app's alarms.

## Fresh readings

| Situation | Screen |
| --- | --- |
| sgv 112 mg/dL, Flat, 3 min old | ![IN RANGE](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/in_range_flat.svg) |
| sgv 150 mg/dL, SingleUp, 0 min old | ![IN RANGE](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/in_range_just_now.svg) |
| sgv 70 mg/dL, FortyFiveDown, 1 min old | ![IN RANGE](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/boundary_low_70_in_range.svg) |
| sgv 69 mg/dL, SingleDown, 2 min old | ![LOW](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/low_69.svg) |
| sgv 55 mg/dL, DoubleDown, 1 min old | ![URGENT LOW](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/urgent_low_55.svg) |
| sgv 39 mg/dL, NONE, 0 min old | ![URGENT LOW](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/sensor_low_sentinel.svg) |
| sgv 180 mg/dL, Flat, 4 min old | ![IN RANGE](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/boundary_high_180_in_range.svg) |
| sgv 181 mg/dL, FortyFiveUp, 4 min old | ![HIGH](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/high_181.svg) |
| sgv 250 mg/dL, DoubleUp, 2 min old | ![URGENT HIGH](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/urgent_high_250.svg) |
| sgv 401 mg/dL, Flat, 0 min old | ![URGENT HIGH](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/sensor_high_sentinel.svg) |
| sgv 130 mg/dL, SomethingNew, 5 min old | ![IN RANGE](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/unknown_direction.svg) |

The boundaries are exact: 70 and 180 are IN RANGE, 69 is LOW, 181 is HIGH, 55 is URGENT LOW, 250 is URGENT HIGH. A 39 is classified URGENT LOW and a 401 URGENT HIGH, but the value line reads "LOW (<40)" and "HIGH (>400)" because the sensor did not measure a number. An unknown direction string keeps the number and prints `?` for the arrow.

## Old or untrustworthy time

| Situation | Screen |
| --- | --- |
| sgv 120 mg/dL, Flat, 15 min old | ![IN RANGE](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/fresh_at_15_minutes.svg) |
| sgv 120 mg/dL, Flat, 16 min old | ![STALE](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/stale_at_16_minutes.svg) |
| sgv 45 mg/dL, SingleDown, 40 min old | ![STALE](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/stale_beats_urgent_low.svg) |
| sgv 120 mg/dL, Flat, 10 min in the future | ![STALE](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/future_dated.svg) |
| sgv 120 mg/dL, Flat, 1 min in the future | ![IN RANGE](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/small_clock_skew_ok.svg) |
| sgv 120 mg/dL, Flat, 899s old | ![IN RANGE](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/fresh_at_14_minutes_59_seconds.svg) |
| sgv 120 mg/dL, Flat, 901s old | ![STALE](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/stale_at_15_minutes_1_second.svg) |
| sgv 120 mg/dL, Flat, 120s in the future | ![IN RANGE](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/future_skew_exactly_2_minutes_ok.svg) |
| sgv 120 mg/dL, Flat, 121s in the future | ![STALE](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/future_skew_2_minutes_1_second_stale.svg) |

Exactly 15 minutes old is still fresh; 16 is STALE. The third row is the most important case in the project: a 45 mg/dL reading that is 40 minutes old shows STALE, not URGENT LOW, because an old low is not evidence of a current low. One minute in the future is tolerated as normal clock skew; ten minutes is not, and the age line reads "time is in the future" so the cause is obvious. The last four rows pin both limits to the second: 14 minutes 59 seconds is fresh and 15 minutes 1 second is STALE (still reading "15 min ago", because the age is floored), and exactly 2 minutes in the future is tolerated while 2 minutes 1 second is not.

## Missing data and outages

| Situation | Screen |
| --- | --- |
| No reading in Nightscout | ![NO DATA](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/no_data.svg) |
| No reading in Nightscout, Nightscout unreachable | ![NO DATA](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/no_data_unreachable.svg) |
| sgv 101 mg/dL, Flat, 7 min old, Nightscout unreachable | ![IN RANGE](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/last_good_while_unreachable.svg) |
| sgv 120 mg/dL, Flat, 32 min old, Nightscout unreachable | ![STALE](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/stale_while_unreachable_stays_four_lines.svg) |
| sgv 402 mg/dL, Flat, 1 min old | ![NO DATA](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/invalid_value_rejected.svg) |
| mbg 120 mg/dL, Flat, 1 min old | ![NO DATA](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/non_sgv_rejected.svg) |
| sgv 1e+30 mg/dL, Flat, 1 min old | ![NO DATA](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/huge_value_rejected.svg) |

When Nightscout cannot be reached, the display does not freeze. A good earlier reading is shown with "Nightscout unreachable" appended and keeps aging; the fourth row shows it passing the stale limit while the site is still down. The STALE screen is already four lines, so "Nightscout unreachable" replaces the "Confirm on primary device" line, which the STALE headline already implies. The first Python version rendered five lines here; the shared vectors caught it.

The last three rows show rejection rather than repair. A 402 is outside the sensor range; an `mbg` entry is a manual meter reading, not a sensor entry; a `1e+30` is a value that once raised an error past the parser and blanked the whole window (HAZ-011). Each is dropped, and with nothing valid left the screen says NO DATA rather than guessing.

## Several entries at once

| Situation | Screen |
| --- | --- |
| sgv 130 mg/dL, Flat, 0 min old; sgv 68 mg/dL, SingleDown, 0 min old; sgv 110 mg/dL, Flat, 5 min old | ![LOW](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/same_timestamp_lower_value_wins.svg) |
| sgv 100 mg/dL, Flat, 10 min old; sgv 140 mg/dL, FortyFiveUp, 1 min old; sgv 90 mg/dL, Flat, 5 min old | ![IN RANGE](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/newest_entry_wins_in_any_order.svg) |
| sgv 1e+30 mg/dL, Flat, 0 min old; sgv 402 mg/dL, Flat, 0 min old; sgv 120.5 mg/dL, Flat, 0 min old; mbg 50 mg/dL, Flat, 0 min old; sgv 115 mg/dL, Flat, 2 min old | ![IN RANGE](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/poisoned_entries_skipped.svg) |
| sgv 402 mg/dL, Flat, 0 min old; sgv 110 mg/dL, Flat, 20 min old | ![STALE](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/rejected_newest_does_not_freshen_older.svg) |
| sgv 402 mg/dL, Flat, 0 min old; mbg 120 mg/dL, Flat, 0 min old | ![NO DATA](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/all_entries_rejected_is_no_data.svg) |

Nightscout returns several entries per fetch. Every one is parsed, bad ones are dropped without taking the rest down, and the newest survivor is shown. Two uploaders writing the same timestamp resolve to the lower value, the conservative choice, whatever order they arrive in. The fourth row matters most: a rejected newest entry must not make a 20-minute-old reading look current, so the screen says STALE.

## Custom thresholds (60 / 80 / 160 / 220 mg/dL, stale after 10 minutes)

| Situation | Screen |
| --- | --- |
| sgv 60 mg/dL, SingleDown, 1 min old | ![URGENT LOW](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/custom_urgent_low_60.svg) |
| sgv 79 mg/dL, FortyFiveDown, 2 min old | ![LOW](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/custom_low_79.svg) |
| sgv 160 mg/dL, Flat, 3 min old | ![IN RANGE](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/custom_in_range_160.svg) |
| sgv 161 mg/dL, FortyFiveUp, 3 min old | ![HIGH](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/custom_high_161.svg) |
| sgv 220 mg/dL, SingleUp, 2 min old | ![URGENT HIGH](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/custom_urgent_high_220.svg) |
| sgv 120 mg/dL, Flat, 10 min old | ![IN RANGE](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/custom_fresh_at_10_minutes.svg) |
| sgv 120 mg/dL, Flat, 11 min old | ![STALE](https://raw.githubusercontent.com/esanacore/lightkeeper/main/docs/img/display-states/custom_stale_after_10_minutes.svg) |

Thresholds are display settings and can be changed. These rows use 60 / 80 / 160 / 220 mg/dL with a 10-minute stale limit and show that every boundary and the stale limit move with them.

## Regenerating the gallery

After any change to `spec/display_vectors.json`, run `python tools/gen_display_gallery.py`. It rewrites `docs/DISPLAY_STATES.md`, every SVG under `docs/img/display-states/`, and the state table in `demo.html`; `tests/test_gallery.py` fails if the committed files differ or a vector is missing from the gallery. The one-commit rule is in [[Contributing]]; the parity tests are in [[Testing and Quality]].

See also [[Safety]] for why each rule exists, and [[Troubleshooting]] for what to do when you see STALE or NO DATA on a real display.

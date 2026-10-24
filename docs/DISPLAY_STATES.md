# Display States

Every screen Lightkeeper can show, drawn at the size of a 2.9" e-paper panel. These images are generated from `spec/display_vectors.json` by `tools/gen_display_gallery.py`, the same cases the Python, firmware, and Swift tests run, so they always match real behavior. Regenerate them after changing a vector.

Rules worth noticing: anything older than 15 minutes, or more than 2 minutes in the future, shows STALE, even when the number would be alarming; sensor out-of-range values show as words, not numbers; and the screen never uses more than four lines.

## Fresh readings

| Situation | Screen |
| --- | --- |
| sgv 112 mg/dL, Flat, 3 min old | ![IN RANGE](img/display-states/in_range_flat.svg) |
| sgv 150 mg/dL, SingleUp, 0 min old | ![IN RANGE](img/display-states/in_range_just_now.svg) |
| sgv 70 mg/dL, FortyFiveDown, 1 min old | ![IN RANGE](img/display-states/boundary_low_70_in_range.svg) |
| sgv 69 mg/dL, SingleDown, 2 min old | ![LOW](img/display-states/low_69.svg) |
| sgv 55 mg/dL, DoubleDown, 1 min old | ![URGENT LOW](img/display-states/urgent_low_55.svg) |
| sgv 39 mg/dL, NONE, 0 min old | ![URGENT LOW](img/display-states/sensor_low_sentinel.svg) |
| sgv 180 mg/dL, Flat, 4 min old | ![IN RANGE](img/display-states/boundary_high_180_in_range.svg) |
| sgv 181 mg/dL, FortyFiveUp, 4 min old | ![HIGH](img/display-states/high_181.svg) |
| sgv 250 mg/dL, DoubleUp, 2 min old | ![URGENT HIGH](img/display-states/urgent_high_250.svg) |
| sgv 401 mg/dL, Flat, 0 min old | ![URGENT HIGH](img/display-states/sensor_high_sentinel.svg) |
| sgv 130 mg/dL, SomethingNew, 5 min old | ![IN RANGE](img/display-states/unknown_direction.svg) |

## Old or untrustworthy time

| Situation | Screen |
| --- | --- |
| sgv 120 mg/dL, Flat, 15 min old | ![IN RANGE](img/display-states/fresh_at_15_minutes.svg) |
| sgv 120 mg/dL, Flat, 16 min old | ![STALE](img/display-states/stale_at_16_minutes.svg) |
| sgv 45 mg/dL, SingleDown, 40 min old | ![STALE](img/display-states/stale_beats_urgent_low.svg) |
| sgv 120 mg/dL, Flat, 10 min in the future | ![STALE](img/display-states/future_dated.svg) |
| sgv 120 mg/dL, Flat, 1 min in the future | ![IN RANGE](img/display-states/small_clock_skew_ok.svg) |
| sgv 120 mg/dL, Flat, 899s old | ![IN RANGE](img/display-states/fresh_at_14_minutes_59_seconds.svg) |
| sgv 120 mg/dL, Flat, 901s old | ![STALE](img/display-states/stale_at_15_minutes_1_second.svg) |
| sgv 120 mg/dL, Flat, 120s in the future | ![IN RANGE](img/display-states/future_skew_exactly_2_minutes_ok.svg) |
| sgv 120 mg/dL, Flat, 121s in the future | ![STALE](img/display-states/future_skew_2_minutes_1_second_stale.svg) |

## Several entries at once

| Situation | Screen |
| --- | --- |
| sgv 130 mg/dL, Flat, 0 min old; sgv 68 mg/dL, SingleDown, 0 min old; sgv 110 mg/dL, Flat, 5 min old | ![LOW](img/display-states/same_timestamp_lower_value_wins.svg) |
| sgv 100 mg/dL, Flat, 10 min old; sgv 140 mg/dL, FortyFiveUp, 1 min old; sgv 90 mg/dL, Flat, 5 min old | ![IN RANGE](img/display-states/newest_entry_wins_in_any_order.svg) |
| sgv 1e+30 mg/dL, Flat, 0 min old; sgv 402 mg/dL, Flat, 0 min old; sgv 120.5 mg/dL, Flat, 0 min old; mbg 50 mg/dL, Flat, 0 min old; sgv 115 mg/dL, Flat, 2 min old | ![IN RANGE](img/display-states/poisoned_entries_skipped.svg) |
| sgv 402 mg/dL, Flat, 0 min old; sgv 110 mg/dL, Flat, 20 min old | ![STALE](img/display-states/rejected_newest_does_not_freshen_older.svg) |
| sgv 402 mg/dL, Flat, 0 min old; mbg 120 mg/dL, Flat, 0 min old | ![NO DATA](img/display-states/all_entries_rejected_is_no_data.svg) |

## Custom thresholds (60 / 80 / 160 / 220 mg/dL, stale after 10 minutes)

| Situation | Screen |
| --- | --- |
| sgv 60 mg/dL, SingleDown, 1 min old | ![URGENT LOW](img/display-states/custom_urgent_low_60.svg) |
| sgv 79 mg/dL, FortyFiveDown, 2 min old | ![LOW](img/display-states/custom_low_79.svg) |
| sgv 160 mg/dL, Flat, 3 min old | ![IN RANGE](img/display-states/custom_in_range_160.svg) |
| sgv 161 mg/dL, FortyFiveUp, 3 min old | ![HIGH](img/display-states/custom_high_161.svg) |
| sgv 220 mg/dL, SingleUp, 2 min old | ![URGENT HIGH](img/display-states/custom_urgent_high_220.svg) |
| sgv 120 mg/dL, Flat, 10 min old | ![IN RANGE](img/display-states/custom_fresh_at_10_minutes.svg) |
| sgv 120 mg/dL, Flat, 11 min old | ![STALE](img/display-states/custom_stale_after_10_minutes.svg) |

## Missing data and outages

| Situation | Screen |
| --- | --- |
| No reading in Nightscout | ![NO DATA](img/display-states/no_data.svg) |
| No reading in Nightscout, Nightscout unreachable | ![NO DATA](img/display-states/no_data_unreachable.svg) |
| sgv 101 mg/dL, Flat, 7 min old, Nightscout unreachable | ![IN RANGE](img/display-states/last_good_while_unreachable.svg) |
| sgv 120 mg/dL, Flat, 32 min old, Nightscout unreachable | ![STALE](img/display-states/stale_while_unreachable_stays_four_lines.svg) |
| sgv 402 mg/dL, Flat, 1 min old | ![NO DATA](img/display-states/invalid_value_rejected.svg) |
| sgv 1e+30 mg/dL, Flat, 1 min old | ![NO DATA](img/display-states/huge_value_rejected.svg) |
| mbg 120 mg/dL, Flat, 1 min old | ![NO DATA](img/display-states/non_sgv_rejected.svg) |

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

# Display States

Every screen Lightkeeper can show, drawn at the size of a 2.9" e-paper panel. These images are generated from `spec/display_vectors.json` by `tools/gen_display_gallery.py`, the same cases the Python, firmware, and Swift tests run, so they always match real behavior. Regenerate them after changing a vector.

Rules worth noticing: anything older than 15 minutes, or more than 2 minutes in the future, shows STALE, even when the number would be alarming; sensor out-of-range values show as words, not numbers; and the screen never uses more than four lines.

![How a reading becomes a word: NO DATA, then STALE before any range check, then the thresholds](../assets/diagrams/classification.svg)

The **Screen** column is the SVG preview (also written by `--svg`), in the brand's Paper and Ink. The **Panel pixels** column is the exact 1-bit bitmap the Raspberry Pi e-paper panel will show, drawn by `lightkeeper.infrastructure.epaper_bitmap` with the project's own font and shown at 2x.

Both columns give every status its word plus a shape, from the same table: IN RANGE is plain; LOW and HIGH get a rule under the headline; URGENT LOW and URGENT HIGH an inverse band; STALE the inverse band, a hatched frame in the margin and the `last:` line struck through; NO DATA, and any headline the table does not know, a dashed frame. Each image's alt text is the screen's own lines, joined by slashes, as the SVG's title reads them.

## Fresh readings

| Situation | Screen | Panel pixels |
| --- | --- | --- |
| sgv 112 mg/dL, Flat, 3 min old | ![IN RANGE / 112 mg/dL -> / 3 min ago](img/display-states/in_range_flat.svg) | ![IN RANGE / 112 mg/dL -> / 3 min ago, panel pixels](img/epaper/in_range_flat.png) |
| sgv 150 mg/dL, SingleUp, 0 min old | ![IN RANGE / 150 mg/dL ^ / just now](img/display-states/in_range_just_now.svg) | ![IN RANGE / 150 mg/dL ^ / just now, panel pixels](img/epaper/in_range_just_now.png) |
| sgv 70 mg/dL, FortyFiveDown, 1 min old | ![IN RANGE / 70 mg/dL \\ / 1 min ago](img/display-states/boundary_low_70_in_range.svg) | ![IN RANGE / 70 mg/dL \\ / 1 min ago, panel pixels](img/epaper/boundary_low_70_in_range.png) |
| sgv 69 mg/dL, SingleDown, 2 min old | ![LOW / 69 mg/dL v / 2 min ago](img/display-states/low_69.svg) | ![LOW / 69 mg/dL v / 2 min ago, panel pixels](img/epaper/low_69.png) |
| sgv 55 mg/dL, DoubleDown, 1 min old | ![URGENT LOW / 55 mg/dL vv / 1 min ago](img/display-states/urgent_low_55.svg) | ![URGENT LOW / 55 mg/dL vv / 1 min ago, panel pixels](img/epaper/urgent_low_55.png) |
| sgv 39 mg/dL, NONE, 0 min old | ![URGENT LOW / LOW (\<40) / just now](img/display-states/sensor_low_sentinel.svg) | ![URGENT LOW / LOW (\<40) / just now, panel pixels](img/epaper/sensor_low_sentinel.png) |
| sgv 180 mg/dL, Flat, 4 min old | ![IN RANGE / 180 mg/dL -> / 4 min ago](img/display-states/boundary_high_180_in_range.svg) | ![IN RANGE / 180 mg/dL -> / 4 min ago, panel pixels](img/epaper/boundary_high_180_in_range.png) |
| sgv 181 mg/dL, FortyFiveUp, 4 min old | ![HIGH / 181 mg/dL / / 4 min ago](img/display-states/high_181.svg) | ![HIGH / 181 mg/dL / / 4 min ago, panel pixels](img/epaper/high_181.png) |
| sgv 250 mg/dL, DoubleUp, 2 min old | ![URGENT HIGH / 250 mg/dL ^^ / 2 min ago](img/display-states/urgent_high_250.svg) | ![URGENT HIGH / 250 mg/dL ^^ / 2 min ago, panel pixels](img/epaper/urgent_high_250.png) |
| sgv 401 mg/dL, Flat, 0 min old | ![URGENT HIGH / HIGH (>400) / just now](img/display-states/sensor_high_sentinel.svg) | ![URGENT HIGH / HIGH (>400) / just now, panel pixels](img/epaper/sensor_high_sentinel.png) |
| sgv 130 mg/dL, SomethingNew, 5 min old | ![IN RANGE / 130 mg/dL ? / 5 min ago](img/display-states/unknown_direction.svg) | ![IN RANGE / 130 mg/dL ? / 5 min ago, panel pixels](img/epaper/unknown_direction.png) |

## Old or untrustworthy time

| Situation | Screen | Panel pixels |
| --- | --- | --- |
| sgv 120 mg/dL, Flat, 15 min old | ![IN RANGE / 120 mg/dL -> / 15 min ago](img/display-states/fresh_at_15_minutes.svg) | ![IN RANGE / 120 mg/dL -> / 15 min ago, panel pixels](img/epaper/fresh_at_15_minutes.png) |
| sgv 120 mg/dL, Flat, 16 min old | ![STALE - DO NOT TRUST / last: 120 mg/dL -> / 16 min ago / Confirm on primary device](img/display-states/stale_at_16_minutes.svg) | ![STALE - DO NOT TRUST / last: 120 mg/dL -> / 16 min ago / Confirm on primary device, panel pixels](img/epaper/stale_at_16_minutes.png) |
| sgv 45 mg/dL, SingleDown, 40 min old | ![STALE - DO NOT TRUST / last: 45 mg/dL v / 40 min ago / Confirm on primary device](img/display-states/stale_beats_urgent_low.svg) | ![STALE - DO NOT TRUST / last: 45 mg/dL v / 40 min ago / Confirm on primary device, panel pixels](img/epaper/stale_beats_urgent_low.png) |
| sgv 120 mg/dL, Flat, 10 min in the future | ![STALE - DO NOT TRUST / last: 120 mg/dL -> / time is in the future / Confirm on primary device](img/display-states/future_dated.svg) | ![STALE - DO NOT TRUST / last: 120 mg/dL -> / time is in the future / Confirm on primary device, panel pixels](img/epaper/future_dated.png) |
| sgv 120 mg/dL, Flat, 1 min in the future | ![IN RANGE / 120 mg/dL -> / just now](img/display-states/small_clock_skew_ok.svg) | ![IN RANGE / 120 mg/dL -> / just now, panel pixels](img/epaper/small_clock_skew_ok.png) |
| sgv 120 mg/dL, Flat, 899s old | ![IN RANGE / 120 mg/dL -> / 14 min ago](img/display-states/fresh_at_14_minutes_59_seconds.svg) | ![IN RANGE / 120 mg/dL -> / 14 min ago, panel pixels](img/epaper/fresh_at_14_minutes_59_seconds.png) |
| sgv 120 mg/dL, Flat, 901s old | ![STALE - DO NOT TRUST / last: 120 mg/dL -> / 15 min ago / Confirm on primary device](img/display-states/stale_at_15_minutes_1_second.svg) | ![STALE - DO NOT TRUST / last: 120 mg/dL -> / 15 min ago / Confirm on primary device, panel pixels](img/epaper/stale_at_15_minutes_1_second.png) |
| sgv 120 mg/dL, Flat, 120s in the future | ![IN RANGE / 120 mg/dL -> / just now](img/display-states/future_skew_exactly_2_minutes_ok.svg) | ![IN RANGE / 120 mg/dL -> / just now, panel pixels](img/epaper/future_skew_exactly_2_minutes_ok.png) |
| sgv 120 mg/dL, Flat, 121s in the future | ![STALE - DO NOT TRUST / last: 120 mg/dL -> / time is in the future / Confirm on primary device](img/display-states/future_skew_2_minutes_1_second_stale.svg) | ![STALE - DO NOT TRUST / last: 120 mg/dL -> / time is in the future / Confirm on primary device, panel pixels](img/epaper/future_skew_2_minutes_1_second_stale.png) |

## Several entries at once

| Situation | Screen | Panel pixels |
| --- | --- | --- |
| sgv 130 mg/dL, Flat, 0 min old; sgv 68 mg/dL, SingleDown, 0 min old; sgv 110 mg/dL, Flat, 5 min old | ![LOW / 68 mg/dL v / just now](img/display-states/same_timestamp_lower_value_wins.svg) | ![LOW / 68 mg/dL v / just now, panel pixels](img/epaper/same_timestamp_lower_value_wins.png) |
| sgv 100 mg/dL, Flat, 10 min old; sgv 140 mg/dL, FortyFiveUp, 1 min old; sgv 90 mg/dL, Flat, 5 min old | ![IN RANGE / 140 mg/dL / / 1 min ago](img/display-states/newest_entry_wins_in_any_order.svg) | ![IN RANGE / 140 mg/dL / / 1 min ago, panel pixels](img/epaper/newest_entry_wins_in_any_order.png) |
| sgv 1e+30 mg/dL, Flat, 0 min old; sgv 402 mg/dL, Flat, 0 min old; sgv 120.5 mg/dL, Flat, 0 min old; mbg 50 mg/dL, Flat, 0 min old; sgv 115 mg/dL, Flat, 2 min old | ![IN RANGE / 115 mg/dL -> / 2 min ago](img/display-states/poisoned_entries_skipped.svg) | ![IN RANGE / 115 mg/dL -> / 2 min ago, panel pixels](img/epaper/poisoned_entries_skipped.png) |
| sgv 402 mg/dL, Flat, 0 min old; sgv 110 mg/dL, Flat, 20 min old | ![STALE - DO NOT TRUST / last: 110 mg/dL -> / 20 min ago / Confirm on primary device](img/display-states/rejected_newest_does_not_freshen_older.svg) | ![STALE - DO NOT TRUST / last: 110 mg/dL -> / 20 min ago / Confirm on primary device, panel pixels](img/epaper/rejected_newest_does_not_freshen_older.png) |
| sgv 402 mg/dL, Flat, 0 min old; mbg 120 mg/dL, Flat, 0 min old | ![NO DATA / Check sensor and phone / Confirm on primary device](img/display-states/all_entries_rejected_is_no_data.svg) | ![NO DATA / Check sensor and phone / Confirm on primary device, panel pixels](img/epaper/all_entries_rejected_is_no_data.png) |

## Custom thresholds (60 / 80 / 160 / 220 mg/dL, stale after 10 minutes)

| Situation | Screen | Panel pixels |
| --- | --- | --- |
| sgv 60 mg/dL, SingleDown, 1 min old | ![URGENT LOW / 60 mg/dL v / 1 min ago](img/display-states/custom_urgent_low_60.svg) | ![URGENT LOW / 60 mg/dL v / 1 min ago, panel pixels](img/epaper/custom_urgent_low_60.png) |
| sgv 79 mg/dL, FortyFiveDown, 2 min old | ![LOW / 79 mg/dL \\ / 2 min ago](img/display-states/custom_low_79.svg) | ![LOW / 79 mg/dL \\ / 2 min ago, panel pixels](img/epaper/custom_low_79.png) |
| sgv 160 mg/dL, Flat, 3 min old | ![IN RANGE / 160 mg/dL -> / 3 min ago](img/display-states/custom_in_range_160.svg) | ![IN RANGE / 160 mg/dL -> / 3 min ago, panel pixels](img/epaper/custom_in_range_160.png) |
| sgv 161 mg/dL, FortyFiveUp, 3 min old | ![HIGH / 161 mg/dL / / 3 min ago](img/display-states/custom_high_161.svg) | ![HIGH / 161 mg/dL / / 3 min ago, panel pixels](img/epaper/custom_high_161.png) |
| sgv 220 mg/dL, SingleUp, 2 min old | ![URGENT HIGH / 220 mg/dL ^ / 2 min ago](img/display-states/custom_urgent_high_220.svg) | ![URGENT HIGH / 220 mg/dL ^ / 2 min ago, panel pixels](img/epaper/custom_urgent_high_220.png) |
| sgv 120 mg/dL, Flat, 10 min old | ![IN RANGE / 120 mg/dL -> / 10 min ago](img/display-states/custom_fresh_at_10_minutes.svg) | ![IN RANGE / 120 mg/dL -> / 10 min ago, panel pixels](img/epaper/custom_fresh_at_10_minutes.png) |
| sgv 120 mg/dL, Flat, 11 min old | ![STALE - DO NOT TRUST / last: 120 mg/dL -> / 11 min ago / Confirm on primary device](img/display-states/custom_stale_after_10_minutes.svg) | ![STALE - DO NOT TRUST / last: 120 mg/dL -> / 11 min ago / Confirm on primary device, panel pixels](img/epaper/custom_stale_after_10_minutes.png) |

## Missing data and outages

| Situation | Screen | Panel pixels |
| --- | --- | --- |
| No reading in Nightscout | ![NO DATA / Check sensor and phone / Confirm on primary device](img/display-states/no_data.svg) | ![NO DATA / Check sensor and phone / Confirm on primary device, panel pixels](img/epaper/no_data.png) |
| No reading in Nightscout, Nightscout unreachable | ![NO DATA / Check sensor and phone / Confirm on primary device / Nightscout unreachable](img/display-states/no_data_unreachable.svg) | ![NO DATA / Check sensor and phone / Confirm on primary device / Nightscout unreachable, panel pixels](img/epaper/no_data_unreachable.png) |
| sgv 101 mg/dL, Flat, 7 min old, Nightscout unreachable | ![IN RANGE / 101 mg/dL -> / 7 min ago / Nightscout unreachable](img/display-states/last_good_while_unreachable.svg) | ![IN RANGE / 101 mg/dL -> / 7 min ago / Nightscout unreachable, panel pixels](img/epaper/last_good_while_unreachable.png) |
| sgv 120 mg/dL, Flat, 32 min old, Nightscout unreachable | ![STALE - DO NOT TRUST / last: 120 mg/dL -> / 32 min ago / Nightscout unreachable](img/display-states/stale_while_unreachable_stays_four_lines.svg) | ![STALE - DO NOT TRUST / last: 120 mg/dL -> / 32 min ago / Nightscout unreachable, panel pixels](img/epaper/stale_while_unreachable_stays_four_lines.png) |
| sgv 402 mg/dL, Flat, 1 min old | ![NO DATA / Check sensor and phone / Confirm on primary device](img/display-states/invalid_value_rejected.svg) | ![NO DATA / Check sensor and phone / Confirm on primary device, panel pixels](img/epaper/invalid_value_rejected.png) |
| sgv 1e+30 mg/dL, Flat, 1 min old | ![NO DATA / Check sensor and phone / Confirm on primary device](img/display-states/huge_value_rejected.svg) | ![NO DATA / Check sensor and phone / Confirm on primary device, panel pixels](img/epaper/huge_value_rejected.png) |
| mbg 120 mg/dL, Flat, 1 min old | ![NO DATA / Check sensor and phone / Confirm on primary device](img/display-states/non_sgv_rejected.svg) | ![NO DATA / Check sensor and phone / Confirm on primary device, panel pixels](img/epaper/non_sgv_rejected.png) |

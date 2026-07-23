# es_pivot_filtered_prior_value_area_acceptance density audit

CSV detail: `research_artifacts/es_pivot_filtered_prior_value_area_acceptance_density_screen_20260620.csv`
Summary CSV: `research_artifacts/es_pivot_filtered_prior_value_area_acceptance_density_summary_20260620.csv`

Strict 2-of-2 pivot alignment was rejected before PnL after observed minimum rates of roughly 12-29 signals/year in the first morning variants. Active filter is fixed before PnL: 5m/15m completed pivots, `min_aligned_timeframes=1`, no opposite checked timeframe, carried prior-session pivots enabled.

| variant_id | entry_combinations | combos_passing_all_windows | min_full/y | min_limited/y | min_wfa90/y | min_latest1y/y | decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| morning_signed_vah_pivot_acceptance_long | 9 | 9 | 66.30 | 61.09 | 66.44 | 67.23 | PASS |
| morning_signed_two_sided_pivot_acceptance_1230 | 9 | 9 | 109.98 | 112.43 | 110.10 | 105.36 | PASS |
| late_morning_large10_two_sided_pivot_acceptance | 9 | 9 | 124.88 | 120.23 | 124.15 | 134.46 | PASS |
| midday_signed_two_sided_pivot_acceptance | 9 | 9 | 126.70 | 129.98 | 128.26 | 115.39 | PASS |
| afternoon_large20_two_sided_pivot_acceptance | 9 | 9 | 119.37 | 112.43 | 120.26 | 115.39 | PASS |

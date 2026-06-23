# ES NQ-confirming VAP AOI breakout density audit

Date: 2026-06-23

Data source: `data/cache/orderflow/es_sierra_footprint_vap_overnight_aoi_nq_leadlag_1m_20110103_20260529_rth_ny.parquet`. The cache is RTH-only; the audit recomputed prior RTH high/low from completed prior sessions and opening range from the first 30 completed RTH minutes.

No PnL, stop, target, or outcome fields were used. Threshold corner: max_profile_distance_ticks=16, min_breakout_ticks=1, close_buffer_ticks=0, min_orderflow_imbalance=0.005, min_footprint_imbalance_volume=1, min_nq_return_bps=0.0, min_nq_signed_imbalance=0.0, max_nq_lag_bps=5.0. Counts are first eligible signal per session to approximate max_trades_per_day=1.

| variant_id | setup_mode | relative_value_window_minutes | end_time | raw_signal_bars | sessions_with_signal | sessions_per_year | first_signal | last_signal | active_years | min_year_signals | first_signal_long_rows | first_signal_short_rows |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all_market_nq30_1500 | all_market_vap_two_sided_breakout | 30 | 15:00:00 | 128244 | 3684 | 239.21 | 2011-01-05 10:05:00 | 2026-05-29 10:01:00 | 16 | 99 | 2029 | 1655 |
| value_area_nq30_1500 | value_area_vap_two_sided_breakout | 30 | 15:00:00 | 118257 | 3678 | 238.82 | 2011-01-03 10:02:00 | 2026-05-29 10:01:00 | 16 | 102 | 2055 | 1623 |
| combined_nq15_1500 | combined_vap_aoi_two_sided_breakout | 15 | 15:00:00 | 127361 | 3645 | 236.68 | 2011-01-05 10:05:00 | 2026-05-29 10:01:00 | 16 | 97 | 2021 | 1624 |
| combined_nq30_1500 | combined_vap_aoi_two_sided_breakout | 30 | 15:00:00 | 122258 | 3639 | 236.29 | 2011-01-05 10:05:00 | 2026-05-29 10:01:00 | 16 | 96 | 2002 | 1637 |
| lvn_nq30_1500 | lvn_vap_two_sided_breakout | 30 | 15:00:00 | 85446 | 3134 | 203.5 | 2011-01-03 10:02:00 | 2026-05-29 10:01:00 | 16 | 93 | 1788 | 1346 |
| prior_extreme_nq30_1500 | prior_extreme_vap_two_sided_breakout | 30 | 15:00:00 | 85202 | 3126 | 202.98 | 2011-01-05 12:36:00 | 2026-05-29 10:01:00 | 16 | 93 | 1783 | 1343 |
| opening_nq30_1200 | opening_range_vap_two_sided_breakout | 30 | 12:00:00 | 26296 | 2124 | 137.92 | 2011-01-05 10:05:00 | 2026-05-29 10:43:00 | 16 | 34 | 1052 | 1072 |
| overnight_nq30_1530 | overnight_extreme_vap_two_sided_breakout | 30 | 15:30:00 | 51588 | 1938 | 125.84 | 2011-01-05 10:07:00 | 2026-05-26 11:50:00 | 16 | 27 | 955 | 983 |

Decision: approve all eight selected mechanics for staged testing before PnL. A ninth dense candidate (`combined_nq60_1500`) was excluded as a lower-density horizon sibling rather than using the expanded variant cap indiscriminately.

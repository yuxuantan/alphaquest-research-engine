# NQ daily short-term reversal density audit - 2026-06-22

Purpose: pre-PnL threshold sanity check for an NQ-only daily short-term reversal campaign. Counts use completed RTH close-to-close returns from the NQ Sierra 1-minute RTH cache and do not inspect strategy PnL.

Source: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`. Sessions: 3813 from 2011-01-03 to 2026-06-12.

| variant | lookback_sessions | gate | threshold | signals | signals_per_year | min_year_count | median_year_count | first_year | last_year |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| prior_1d_loss_reversal_long_1000 | 1 | min_abs_reversal_return_pct | 0.0075 | 740 | 47.93 | 15 | 45.5 | 2011 | 2026 |
| prior_1d_loss_reversal_long_1000 | 1 | min_abs_reversal_return_pct | 0.01 | 574 | 37.18 | 10 | 33.5 | 2011 | 2026 |
| prior_1d_loss_reversal_long_1000 | 1 | min_abs_reversal_return_pct | 0.0125 | 455 | 29.47 | 8 | 26.5 | 2011 | 2026 |
| prior_1d_gain_reversal_short_1000 | 1 | min_abs_reversal_return_pct | 0.0075 | 952 | 61.66 | 35 | 63 | 2011 | 2026 |
| prior_1d_gain_reversal_short_1000 | 1 | min_abs_reversal_return_pct | 0.01 | 693 | 44.89 | 15 | 42.5 | 2011 | 2026 |
| prior_1d_gain_reversal_short_1000 | 1 | min_abs_reversal_return_pct | 0.0125 | 500 | 32.39 | 6 | 30 | 2011 | 2026 |
| prior_3d_two_sided_reversal_1130 | 3 | min_abs_reversal_return_pct | 0.015 | 1591 | 103.05 | 44 | 99.5 | 2011 | 2026 |
| prior_3d_two_sided_reversal_1130 | 3 | min_abs_reversal_return_pct | 0.02 | 1097 | 71.06 | 16 | 64 | 2011 | 2026 |
| prior_3d_two_sided_reversal_1130 | 3 | min_abs_reversal_return_pct | 0.025 | 748 | 48.45 | 4 | 41 | 2011 | 2026 |
| prior_5d_two_sided_reversal_1330 | 5 | min_abs_reversal_return_pct | 0.02 | 1524 | 98.71 | 45 | 93.5 | 2011 | 2026 |
| prior_5d_two_sided_reversal_1330 | 5 | min_abs_reversal_return_pct | 0.025 | 1161 | 75.2 | 20 | 70.5 | 2011 | 2026 |
| prior_5d_two_sided_reversal_1330 | 5 | min_abs_reversal_return_pct | 0.03 | 869 | 56.29 | 5 | 47 | 2011 | 2026 |
| vol_norm_5d_two_sided_reversal_1200 | 5 | min_reversal_zscore | 0.6 | 2427 | 157.2 | 66 | 155 | 2011 | 2026 |
| vol_norm_5d_two_sided_reversal_1200 | 5 | min_reversal_zscore | 0.85 | 1961 | 127.02 | 53 | 126 | 2011 | 2026 |
| vol_norm_5d_two_sided_reversal_1200 | 5 | min_reversal_zscore | 1.1 | 1546 | 100.14 | 45 | 99 | 2011 | 2026 |

Decision: thresholds have sufficient raw signal density for staged testing. Parameter grids are frozen before NQ PnL is evaluated.

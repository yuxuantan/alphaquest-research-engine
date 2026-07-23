# NQ Morning Trend Lunch Reversal Orderflow Density Audit

Generated on 2026-06-30 before any NQ PnL testing for `nq_morning_trend_lunch_reversal_orderflow`.

Input: completed 5-minute NQ RTH bars from `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet` via `propstack.data.pipeline.prepare_data`, using a vectorized equivalent of `MorningTrendLunchReversalOrderflowEntry`.

Availability rule: RTH open anchor, morning extension, signal-bar body, and aggregate counterflow all use completed bars only; no return, PnL, future high/low, final VWAP, final range, or future orderflow was inspected.

Full window: 2011-01-03 to 2026-06-12, 3813 sessions, 15.44 years.
Limited-core density proxy window: 2011-02-22 to 2012-09-07, 371 sessions, 1.54 years.
Latest window: 2025-06-09 to 2026-06-12, 252 sessions.

| Variant | Flow | Morning ticks | Imbalance | Full/year | Limited/year | Latest signals | Decision |
|---|---|---:|---:|---:|---:|---:|---|
| early_afternoon_large20_two_sided_reversal_1400 | large20 | 8 | 0.0 | 203.41 | 219.54 | 209 | PASS |
| early_afternoon_large20_two_sided_reversal_1400 | large20 | 8 | 0.02 | 201.34 | 219.54 | 208 | PASS |
| early_afternoon_large20_two_sided_reversal_1400 | large20 | 8 | 0.04 | 200.50 | 218.89 | 208 | PASS |
| early_afternoon_large20_two_sided_reversal_1400 | large20 | 12 | 0.0 | 199.79 | 213.71 | 207 | PASS |
| early_afternoon_large20_two_sided_reversal_1400 | large20 | 12 | 0.02 | 197.78 | 213.71 | 206 | PASS |
| early_afternoon_large20_two_sided_reversal_1400 | large20 | 12 | 0.04 | 196.94 | 213.06 | 206 | PASS |
| early_afternoon_large20_two_sided_reversal_1400 | large20 | 16 | 0.0 | 196.03 | 207.23 | 207 | PASS |
| early_afternoon_large20_two_sided_reversal_1400 | large20 | 16 | 0.02 | 194.02 | 206.59 | 206 | PASS |
| early_afternoon_large20_two_sided_reversal_1400 | large20 | 16 | 0.04 | 193.12 | 205.94 | 206 | PASS |
| late_morning_signed_down_extension_long_1130 | signed_volume | 8 | 0.0 | 128.81 | 115.92 | 125 | PASS |
| late_morning_signed_down_extension_long_1130 | signed_volume | 8 | 0.02 | 126.02 | 113.33 | 118 | PASS |
| late_morning_signed_down_extension_long_1130 | signed_volume | 8 | 0.04 | 118.71 | 110.74 | 106 | PASS |
| late_morning_signed_down_extension_long_1130 | signed_volume | 12 | 0.0 | 125.12 | 106.21 | 125 | PASS |
| late_morning_signed_down_extension_long_1130 | signed_volume | 12 | 0.02 | 122.07 | 102.97 | 118 | PASS |
| late_morning_signed_down_extension_long_1130 | signed_volume | 12 | 0.04 | 114.56 | 99.73 | 106 | PASS |
| late_morning_signed_down_extension_long_1130 | signed_volume | 16 | 0.0 | 120.52 | 100.38 | 124 | PASS |
| late_morning_signed_down_extension_long_1130 | signed_volume | 16 | 0.02 | 117.67 | 97.79 | 118 | PASS |
| late_morning_signed_down_extension_long_1130 | signed_volume | 16 | 0.04 | 110.74 | 94.55 | 106 | PASS |
| late_morning_signed_up_extension_short_1130 | signed_volume | 8 | 0.0 | 144.09 | 137.29 | 159 | PASS |
| late_morning_signed_up_extension_short_1130 | signed_volume | 8 | 0.02 | 141.37 | 134.70 | 156 | PASS |
| late_morning_signed_up_extension_short_1130 | signed_volume | 8 | 0.04 | 136.19 | 128.87 | 142 | PASS |
| late_morning_signed_up_extension_short_1130 | signed_volume | 12 | 0.0 | 140.21 | 128.87 | 159 | PASS |
| late_morning_signed_up_extension_short_1130 | signed_volume | 12 | 0.02 | 137.94 | 126.28 | 156 | PASS |
| late_morning_signed_up_extension_short_1130 | signed_volume | 12 | 0.04 | 132.76 | 121.10 | 141 | PASS |
| late_morning_signed_up_extension_short_1130 | signed_volume | 16 | 0.0 | 136.26 | 118.51 | 159 | PASS |
| late_morning_signed_up_extension_short_1130 | signed_volume | 16 | 0.02 | 134.05 | 115.92 | 156 | PASS |
| late_morning_signed_up_extension_short_1130 | signed_volume | 16 | 0.04 | 129.07 | 110.74 | 141 | PASS |
| lunch_large10_two_sided_reversal_1300 | large10 | 8 | 0.0 | 240.72 | 236.38 | 250 | PASS |
| lunch_large10_two_sided_reversal_1300 | large10 | 8 | 0.02 | 239.74 | 236.38 | 250 | PASS |
| lunch_large10_two_sided_reversal_1300 | large10 | 8 | 0.04 | 239.16 | 235.08 | 248 | PASS |
| lunch_large10_two_sided_reversal_1300 | large10 | 12 | 0.0 | 237.15 | 229.25 | 249 | PASS |
| lunch_large10_two_sided_reversal_1300 | large10 | 12 | 0.02 | 236.18 | 229.25 | 249 | PASS |
| lunch_large10_two_sided_reversal_1300 | large10 | 12 | 0.04 | 235.47 | 227.96 | 247 | PASS |
| lunch_large10_two_sided_reversal_1300 | large10 | 16 | 0.0 | 232.88 | 224.07 | 249 | PASS |
| lunch_large10_two_sided_reversal_1300 | large10 | 16 | 0.02 | 231.84 | 224.07 | 249 | PASS |
| lunch_large10_two_sided_reversal_1300 | large10 | 16 | 0.04 | 231.00 | 222.78 | 247 | PASS |
| lunch_signed_two_sided_reversal_1230 | signed_volume | 8 | 0.0 | 243.11 | 233.14 | 252 | PASS |
| lunch_signed_two_sided_reversal_1230 | signed_volume | 8 | 0.02 | 242.01 | 231.84 | 251 | PASS |
| lunch_signed_two_sided_reversal_1230 | signed_volume | 8 | 0.04 | 237.09 | 231.20 | 238 | PASS |
| lunch_signed_two_sided_reversal_1230 | signed_volume | 12 | 0.0 | 238.71 | 225.37 | 252 | PASS |
| lunch_signed_two_sided_reversal_1230 | signed_volume | 12 | 0.02 | 237.22 | 222.13 | 251 | PASS |
| lunch_signed_two_sided_reversal_1230 | signed_volume | 12 | 0.04 | 232.17 | 220.83 | 238 | PASS |
| lunch_signed_two_sided_reversal_1230 | signed_volume | 16 | 0.0 | 234.30 | 218.24 | 252 | PASS |
| lunch_signed_two_sided_reversal_1230 | signed_volume | 16 | 0.02 | 233.01 | 216.30 | 251 | PASS |
| lunch_signed_two_sided_reversal_1230 | signed_volume | 16 | 0.04 | 227.37 | 215.01 | 238 | PASS |

Decision: PASS. 45/45 declared entry rows cleared the full-history, limited-core, and latest-window density gates.

Minimum full-history density: 110.74 signals/year. Minimum limited-core density: 94.55 signals/year. Minimum latest-window count: 106.

No return, PnL, trade outcome, stop, target, or equity data was inspected during this screen.

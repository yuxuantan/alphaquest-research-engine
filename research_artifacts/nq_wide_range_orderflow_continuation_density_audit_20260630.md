# NQ Wide Range Orderflow Continuation Density Audit

Generated on 2026-06-30 before any NQ PnL testing for `nq_wide_range_orderflow_continuation`.

Input: completed 5-minute NQ RTH bars from `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet` via `propstack.data.pipeline.prepare_data`, using a vectorized equivalent of `WideRangeOrderflowContinuationEntry`.

Availability rule: bar range, body, close location, rolling volume ratio, and aggregate orderflow use only completed signal bars and prior rolling-volume history. No return, PnL, future high/low, final VWAP, final range, or future orderflow was inspected.

Full window: 2011-01-03 to 2026-06-12, 3813 sessions, 15.44 years.
Limited-core density proxy window: 2011-02-22 to 2012-09-07, 371 sessions, 1.54 years.
Latest window: 2025-06-09 to 2026-06-12, 252 sessions.

| Variant | Flow | Range ticks | Imbalance | Full/year | Limited/year | Latest signals | Decision |
|---|---|---:|---:|---:|---:|---:|---|
| afternoon_large20_range_expansion_long | large20 | 4 | 0.0 | 159.92 | 173.87 | 125 | PASS |
| afternoon_large20_range_expansion_long | large20 | 4 | 0.02 | 157.98 | 171.92 | 123 | PASS |
| afternoon_large20_range_expansion_long | large20 | 4 | 0.04 | 156.75 | 169.33 | 123 | PASS |
| afternoon_large20_range_expansion_long | large20 | 8 | 0.0 | 158.37 | 166.73 | 125 | PASS |
| afternoon_large20_range_expansion_long | large20 | 8 | 0.02 | 156.36 | 164.14 | 123 | PASS |
| afternoon_large20_range_expansion_long | large20 | 8 | 0.04 | 155.19 | 161.54 | 123 | PASS |
| afternoon_large20_range_expansion_long | large20 | 12 | 0.0 | 149.43 | 139.48 | 125 | PASS |
| afternoon_large20_range_expansion_long | large20 | 12 | 0.02 | 147.23 | 136.89 | 123 | PASS |
| afternoon_large20_range_expansion_long | large20 | 12 | 0.04 | 145.87 | 134.29 | 123 | PASS |
| afternoon_large20_range_expansion_short | large20 | 4 | 0.0 | 153.96 | 171.27 | 120 | PASS |
| afternoon_large20_range_expansion_short | large20 | 4 | 0.02 | 151.37 | 169.97 | 118 | PASS |
| afternoon_large20_range_expansion_short | large20 | 4 | 0.04 | 150.40 | 168.68 | 118 | PASS |
| afternoon_large20_range_expansion_short | large20 | 8 | 0.0 | 152.93 | 168.03 | 120 | PASS |
| afternoon_large20_range_expansion_short | large20 | 8 | 0.02 | 150.34 | 166.73 | 118 | PASS |
| afternoon_large20_range_expansion_short | large20 | 8 | 0.04 | 149.36 | 165.43 | 118 | PASS |
| afternoon_large20_range_expansion_short | large20 | 12 | 0.0 | 143.92 | 138.19 | 120 | PASS |
| afternoon_large20_range_expansion_short | large20 | 12 | 0.02 | 141.59 | 137.54 | 118 | PASS |
| afternoon_large20_range_expansion_short | large20 | 12 | 0.04 | 140.62 | 136.24 | 118 | PASS |
| midday_large10_range_expansion_twosided | large10 | 4 | 0.0 | 221.13 | 217.98 | 227 | PASS |
| midday_large10_range_expansion_twosided | large10 | 4 | 0.02 | 218.87 | 217.33 | 225 | PASS |
| midday_large10_range_expansion_twosided | large10 | 4 | 0.04 | 217.63 | 214.74 | 224 | PASS |
| midday_large10_range_expansion_twosided | large10 | 8 | 0.0 | 220.61 | 216.68 | 227 | PASS |
| midday_large10_range_expansion_twosided | large10 | 8 | 0.02 | 218.28 | 216.04 | 225 | PASS |
| midday_large10_range_expansion_twosided | large10 | 8 | 0.04 | 217.05 | 213.44 | 224 | PASS |
| midday_large10_range_expansion_twosided | large10 | 12 | 0.0 | 213.36 | 195.28 | 227 | PASS |
| midday_large10_range_expansion_twosided | large10 | 12 | 0.02 | 210.90 | 193.98 | 225 | PASS |
| midday_large10_range_expansion_twosided | large10 | 12 | 0.04 | 209.60 | 192.68 | 224 | PASS |
| morning_signed_range_expansion_long | signed_volume | 4 | 0.0 | 226.31 | 209.55 | 236 | PASS |
| morning_signed_range_expansion_long | signed_volume | 4 | 0.02 | 217.25 | 202.41 | 223 | PASS |
| morning_signed_range_expansion_long | signed_volume | 4 | 0.04 | 200.15 | 190.73 | 192 | PASS |
| morning_signed_range_expansion_long | signed_volume | 8 | 0.0 | 226.25 | 209.55 | 236 | PASS |
| morning_signed_range_expansion_long | signed_volume | 8 | 0.02 | 217.18 | 202.41 | 223 | PASS |
| morning_signed_range_expansion_long | signed_volume | 8 | 0.04 | 200.08 | 190.73 | 192 | PASS |
| morning_signed_range_expansion_long | signed_volume | 12 | 0.0 | 225.73 | 206.95 | 236 | PASS |
| morning_signed_range_expansion_long | signed_volume | 12 | 0.02 | 216.53 | 199.82 | 223 | PASS |
| morning_signed_range_expansion_long | signed_volume | 12 | 0.04 | 199.43 | 188.14 | 192 | PASS |
| morning_signed_range_expansion_short | signed_volume | 4 | 0.0 | 218.15 | 203.71 | 233 | PASS |
| morning_signed_range_expansion_short | signed_volume | 4 | 0.02 | 209.34 | 193.98 | 221 | PASS |
| morning_signed_range_expansion_short | signed_volume | 4 | 0.04 | 192.70 | 184.90 | 196 | PASS |
| morning_signed_range_expansion_short | signed_volume | 8 | 0.0 | 218.15 | 203.71 | 233 | PASS |
| morning_signed_range_expansion_short | signed_volume | 8 | 0.02 | 209.34 | 193.98 | 221 | PASS |
| morning_signed_range_expansion_short | signed_volume | 8 | 0.04 | 192.70 | 184.90 | 196 | PASS |
| morning_signed_range_expansion_short | signed_volume | 12 | 0.0 | 217.76 | 202.41 | 233 | PASS |
| morning_signed_range_expansion_short | signed_volume | 12 | 0.02 | 208.95 | 192.68 | 221 | PASS |
| morning_signed_range_expansion_short | signed_volume | 12 | 0.04 | 192.18 | 182.95 | 196 | PASS |

Decision: PASS. 45/45 declared entry rows cleared the full-history, limited-core, and latest-window density gates.

Minimum full-history density: 140.62 signals/year. Minimum limited-core density: 134.29 signals/year. Minimum latest-window count: 118.

No return, PnL, trade outcome, stop, target, or equity data was inspected during this screen.

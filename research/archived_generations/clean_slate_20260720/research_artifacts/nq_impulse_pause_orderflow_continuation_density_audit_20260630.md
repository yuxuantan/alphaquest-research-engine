# NQ Impulse Pause Orderflow Continuation Density Audit

Generated on 2026-06-30 before any NQ PnL testing for `nq_impulse_pause_orderflow_continuation`.

Input: completed 5-minute NQ RTH bars from `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet` via `propstack.data.pipeline.prepare_data`, using a vectorized equivalent of `ImpulsePauseOrderflowContinuationEntry`.

Availability rule: impulse and pause windows use prior completed bars; breakout close and aggregate orderflow use only the completed signal bar. No return, PnL, future high/low, final VWAP, final range, or future orderflow was inspected.

Full window: 2011-01-03 to 2026-06-12, 3813 sessions, 15.44 years.
Limited-core density proxy window: 2011-02-22 to 2012-09-06, 370 sessions, 1.54 years.
Latest window: 2025-06-09 to 2026-06-12, 252 sessions.

| Variant | Flow | Impulse ticks | Imbalance | Full/year | Limited/year | Latest signals | Decision |
|---|---|---:|---:|---:|---:|---:|---|
| afternoon_large10_two_sided_impulse_pause_breakout_1530 | large10 | 6 | 0.0 | 202.48 | 191.72 | 204 | PASS |
| afternoon_large10_two_sided_impulse_pause_breakout_1530 | large10 | 6 | 0.03 | 199.17 | 187.17 | 202 | PASS |
| afternoon_large10_two_sided_impulse_pause_breakout_1530 | large10 | 6 | 0.06 | 197.10 | 184.57 | 200 | PASS |
| afternoon_large10_two_sided_impulse_pause_breakout_1530 | large10 | 10 | 0.0 | 193.86 | 167.03 | 204 | PASS |
| afternoon_large10_two_sided_impulse_pause_breakout_1530 | large10 | 10 | 0.03 | 191.01 | 163.78 | 202 | PASS |
| afternoon_large10_two_sided_impulse_pause_breakout_1530 | large10 | 10 | 0.06 | 189.13 | 161.83 | 200 | PASS |
| afternoon_large10_two_sided_impulse_pause_breakout_1530 | large10 | 14 | 0.0 | 181.94 | 139.08 | 203 | PASS |
| afternoon_large10_two_sided_impulse_pause_breakout_1530 | large10 | 14 | 0.03 | 178.84 | 134.53 | 202 | PASS |
| afternoon_large10_two_sided_impulse_pause_breakout_1530 | large10 | 14 | 0.06 | 176.83 | 133.23 | 200 | PASS |
| full_session_signed_two_sided_impulse_pause_breakout_1530 | signed_volume | 6 | 0.0 | 231.04 | 220.97 | 235 | PASS |
| full_session_signed_two_sided_impulse_pause_breakout_1530 | signed_volume | 6 | 0.02 | 228.90 | 219.02 | 233 | PASS |
| full_session_signed_two_sided_impulse_pause_breakout_1530 | signed_volume | 6 | 0.04 | 224.31 | 217.72 | 220 | PASS |
| full_session_signed_two_sided_impulse_pause_breakout_1530 | signed_volume | 10 | 0.0 | 224.95 | 206.02 | 234 | PASS |
| full_session_signed_two_sided_impulse_pause_breakout_1530 | signed_volume | 10 | 0.02 | 222.56 | 203.42 | 232 | PASS |
| full_session_signed_two_sided_impulse_pause_breakout_1530 | signed_volume | 10 | 0.04 | 217.38 | 201.47 | 219 | PASS |
| full_session_signed_two_sided_impulse_pause_breakout_1530 | signed_volume | 14 | 0.0 | 217.50 | 188.47 | 234 | PASS |
| full_session_signed_two_sided_impulse_pause_breakout_1530 | signed_volume | 14 | 0.02 | 215.11 | 186.52 | 232 | PASS |
| full_session_signed_two_sided_impulse_pause_breakout_1530 | signed_volume | 14 | 0.04 | 209.28 | 183.27 | 219 | PASS |
| late_morning_large10_two_sided_impulse_pause_breakout_1230 | large10 | 8 | 0.0 | 191.27 | 183.92 | 198 | PASS |
| late_morning_large10_two_sided_impulse_pause_breakout_1230 | large10 | 8 | 0.03 | 188.10 | 181.33 | 198 | PASS |
| late_morning_large10_two_sided_impulse_pause_breakout_1230 | large10 | 8 | 0.06 | 185.51 | 177.43 | 195 | PASS |
| late_morning_large10_two_sided_impulse_pause_breakout_1230 | large10 | 12 | 0.0 | 184.92 | 170.28 | 198 | PASS |
| late_morning_large10_two_sided_impulse_pause_breakout_1230 | large10 | 12 | 0.03 | 181.75 | 167.03 | 198 | PASS |
| late_morning_large10_two_sided_impulse_pause_breakout_1230 | large10 | 12 | 0.06 | 178.97 | 162.48 | 195 | PASS |
| late_morning_large10_two_sided_impulse_pause_breakout_1230 | large10 | 16 | 0.0 | 177.28 | 149.48 | 197 | PASS |
| late_morning_large10_two_sided_impulse_pause_breakout_1230 | large10 | 16 | 0.03 | 174.30 | 146.23 | 197 | PASS |
| late_morning_large10_two_sided_impulse_pause_breakout_1230 | large10 | 16 | 0.06 | 171.39 | 141.68 | 194 | PASS |
| midday_signed_two_sided_impulse_pause_breakout_1400 | signed_volume | 6 | 0.0 | 217.63 | 204.07 | 221 | PASS |
| midday_signed_two_sided_impulse_pause_breakout_1400 | signed_volume | 6 | 0.02 | 214.46 | 201.47 | 214 | PASS |
| midday_signed_two_sided_impulse_pause_breakout_1400 | signed_volume | 6 | 0.04 | 207.85 | 198.22 | 199 | PASS |
| midday_signed_two_sided_impulse_pause_breakout_1400 | signed_volume | 10 | 0.0 | 211.61 | 187.82 | 221 | PASS |
| midday_signed_two_sided_impulse_pause_breakout_1400 | signed_volume | 10 | 0.02 | 208.50 | 185.87 | 214 | PASS |
| midday_signed_two_sided_impulse_pause_breakout_1400 | signed_volume | 10 | 0.04 | 201.89 | 183.27 | 199 | PASS |
| midday_signed_two_sided_impulse_pause_breakout_1400 | signed_volume | 14 | 0.0 | 202.41 | 167.68 | 220 | PASS |
| midday_signed_two_sided_impulse_pause_breakout_1400 | signed_volume | 14 | 0.02 | 199.30 | 165.73 | 212 | PASS |
| midday_signed_two_sided_impulse_pause_breakout_1400 | signed_volume | 14 | 0.04 | 192.63 | 163.13 | 197 | PASS |
| morning_signed_two_sided_impulse_pause_breakout_1130 | signed_volume | 6 | 0.0 | 173.65 | 164.43 | 185 | PASS |
| morning_signed_two_sided_impulse_pause_breakout_1130 | signed_volume | 6 | 0.02 | 166.46 | 161.18 | 169 | PASS |
| morning_signed_two_sided_impulse_pause_breakout_1130 | signed_volume | 6 | 0.04 | 153.06 | 151.43 | 142 | PASS |
| morning_signed_two_sided_impulse_pause_breakout_1130 | signed_volume | 10 | 0.0 | 168.99 | 158.58 | 185 | PASS |
| morning_signed_two_sided_impulse_pause_breakout_1130 | signed_volume | 10 | 0.02 | 161.61 | 154.68 | 169 | PASS |
| morning_signed_two_sided_impulse_pause_breakout_1130 | signed_volume | 10 | 0.04 | 148.46 | 143.63 | 142 | PASS |
| morning_signed_two_sided_impulse_pause_breakout_1130 | signed_volume | 14 | 0.0 | 162.64 | 140.38 | 185 | PASS |
| morning_signed_two_sided_impulse_pause_breakout_1130 | signed_volume | 14 | 0.02 | 155.58 | 137.78 | 169 | PASS |
| morning_signed_two_sided_impulse_pause_breakout_1130 | signed_volume | 14 | 0.04 | 142.43 | 129.33 | 142 | PASS |

Decision: PASS. 45/45 declared entry rows cleared the full-history, limited-core, and latest-window density gates.

Minimum full-history density: 142.43 signals/year. Minimum limited-core density: 129.33 signals/year. Minimum latest-window count: 142.

No return, PnL, trade outcome, stop, target, or equity data was inspected during this screen.

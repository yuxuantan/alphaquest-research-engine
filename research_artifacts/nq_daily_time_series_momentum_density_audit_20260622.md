# NQ Daily Time-Series Momentum Density Audit

Generated on 2026-06-22 before any NQ PnL testing for `nq_daily_time_series_momentum`.

Input: completed NQ RTH closes derived from `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`.

Availability rule: a signal session can only use RTH closes recorded before that session. The current session final close is not available.

| Variant | Lookback | Threshold grid | Signals range | Signals/year range |
|---|---:|---:|---:|---:|
| short_5d_continuation_two_sided_1000 | 5 sessions | abs return >= 0.010, 0.015, 0.020 | 1373-2386 | 88.93-154.55 |
| twenty_day_trend_two_sided_1000 | 20 sessions | abs return >= 0.025, 0.040, 0.055 | 993-2371 | 64.32-153.57 |
| sixty_day_trend_two_sided_1030 | 60 sessions | abs return >= 0.050, 0.075, 0.100 | 940-2246 | 60.89-145.48 |
| twenty_day_long_only_1000 | 20 sessions | positive return >= 0.025, 0.040, 0.055 | 665-1650 | 43.07-106.87 |
| vol_norm_20d_trend_two_sided_1130 | 20 sessions | abs z-score >= 0.50, 0.75, 1.00 | 1441-2485 | 93.34-160.96 |

Decision: approve for authoring. Thresholds are selected from completed-close signal density only; no PnL or intraday outcome data was inspected during this screen.

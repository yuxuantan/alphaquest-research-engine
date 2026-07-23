# ES Trend-Aligned Orderflow Continuation Density Audit - 2026-06-17

Purpose: pre-PnL trade-frequency gate before testing `es_trend_aligned_orderflow_continuation`.

Data: local Sierra aggregate orderflow cache only, `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`.

Prepared bars: 5-minute RTH bars, `2011-01-03` through `2026-06-09`, `America/New_York`.

Screening rule: count sessions where completed price action at the signal close has HH/HL or LH/LL structure on both declared horizons and completed signal-bar aggregate orderflow is aligned. No PnL, stop, target, or post-signal information was used.

Declared entry grid for all variants:

- `entry.params.min_orderflow_imbalance`: `[0.005, 0.01]`
- `entry.params.min_trend_move_ticks`: `[0, 1]`

Density results are annualized over 15.4305 years. The four values are ordered as `(0.005, 0 ticks)`, `(0.005, 1 tick)`, `(0.01, 0 ticks)`, `(0.01, 1 tick)`.

| Variant | Signal close ET | Trend horizons | Flow mode | Annualized signal counts |
|---|---:|---:|---|---:|
| `morning_15_30_large20_trend_flow_1030` | 10:30 | 15m / 30m | large20 | 66.75, 60.40, 65.97, 59.82 |
| `late_morning_15_30_signed_trend_flow_1130` | 11:30 | 15m / 30m | signed_volume | 63.58, 53.98, 61.57, 52.10 |
| `midday_15_30_large10_trend_flow_1230` | 12:30 | 15m / 30m | large10 | 66.75, 53.40, 65.52, 52.36 |
| `afternoon_30_60_large20_trend_flow_1400` | 14:00 | 30m / 60m | large20 | 66.62, 56.84, 65.71, 55.99 |
| `late_day_30_60_large10_trend_flow_1430` | 14:30 | 30m / 60m | large10 | 64.55, 54.63, 64.16, 54.44 |

Decision: approve these five variants for staged testing because every declared entry corner is above roughly 52 trades/year before stop/target filtering. The density screen is not evidence of profitability.

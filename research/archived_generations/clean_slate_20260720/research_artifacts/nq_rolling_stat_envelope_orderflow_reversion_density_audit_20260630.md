# NQ Rolling Statistical Envelope Orderflow Reversion Density Audit

Generated on 2026-06-30 before any NQ PnL testing for `nq_rolling_stat_envelope_orderflow_reversion`.

Input: completed NQ RTH bars from `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet` prepared through `propstack.data.pipeline.prepare_data` at each variant timeframe.

Availability rule: rolling close envelope statistics use only prior completed bars; same-bar orderflow is read only after the signal bar close; staged execution can enter no earlier than the next bar open.

Full window: 2011-01-03 to 2026-06-12, 3813 sessions, 15.44 calendar years.
Limited-core density proxy window: 2011-02-22 to 2012-09-07, 371 sessions, 1.54 calendar years.
Latest window: 2025-06-09 to 2026-06-12, 252 sessions.

Gate: each declared entry row must produce at least 50 signals/year in full history, at least 50 signals/year in the limited-core window, and at least 50 signals in the latest 252 sessions before any PnL is inspected.

## Variant Summary

| Variant | Entry combos | Passing rows | Min full/year | Min limited/year | Min latest signals | Decision |
|---|---:|---:|---:|---:|---:|---|
| afternoon_5m_large20_24bar_reversion_1500 | 9 | 9 | 234.54 | 236.15 | 233 | PASS |
| all_day_1m_signed_30bar_reversion_1530 | 9 | 9 | 246.98 | 240.69 | 252 | PASS |
| late_morning_5m_large10_12bar_reversion_1230 | 9 | 9 | 242.64 | 237.44 | 247 | PASS |
| midday_5m_signed_18bar_reversion_1400 | 9 | 9 | 245.75 | 240.69 | 249 | PASS |
| morning_5m_signed_6bar_reversion_1130 | 9 | 9 | 245.10 | 240.69 | 248 | PASS |

## Entry Rows

| Variant | TF | Mode | Lookback | Band z | Min imbalance | Full/year | Limited/year | Latest signals | Decision |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| afternoon_5m_large20_24bar_reversion_1500 | 5m | large20 | 24 | 1.00 | 0.00 | 243.93 | 240.04 | 249 | PASS |
| afternoon_5m_large20_24bar_reversion_1500 | 5m | large20 | 24 | 1.00 | 0.05 | 243.54 | 240.04 | 249 | PASS |
| afternoon_5m_large20_24bar_reversion_1500 | 5m | large20 | 24 | 1.00 | 0.10 | 243.35 | 240.04 | 249 | PASS |
| afternoon_5m_large20_24bar_reversion_1500 | 5m | large20 | 24 | 1.25 | 0.00 | 241.15 | 238.74 | 244 | PASS |
| afternoon_5m_large20_24bar_reversion_1500 | 5m | large20 | 24 | 1.25 | 0.05 | 240.43 | 238.74 | 244 | PASS |
| afternoon_5m_large20_24bar_reversion_1500 | 5m | large20 | 24 | 1.25 | 0.10 | 240.18 | 238.74 | 244 | PASS |
| afternoon_5m_large20_24bar_reversion_1500 | 5m | large20 | 24 | 1.50 | 0.00 | 236.48 | 236.80 | 234 | PASS |
| afternoon_5m_large20_24bar_reversion_1500 | 5m | large20 | 24 | 1.50 | 0.05 | 235.19 | 236.15 | 233 | PASS |
| afternoon_5m_large20_24bar_reversion_1500 | 5m | large20 | 24 | 1.50 | 0.10 | 234.54 | 236.15 | 233 | PASS |
| all_day_1m_signed_30bar_reversion_1530 | 1m | signed | 30 | 1.50 | 0.00 | 246.98 | 240.69 | 252 | PASS |
| all_day_1m_signed_30bar_reversion_1530 | 1m | signed | 30 | 1.50 | 0.05 | 246.98 | 240.69 | 252 | PASS |
| all_day_1m_signed_30bar_reversion_1530 | 1m | signed | 30 | 1.50 | 0.10 | 246.98 | 240.69 | 252 | PASS |
| all_day_1m_signed_30bar_reversion_1530 | 1m | signed | 30 | 1.75 | 0.00 | 246.98 | 240.69 | 252 | PASS |
| all_day_1m_signed_30bar_reversion_1530 | 1m | signed | 30 | 1.75 | 0.05 | 246.98 | 240.69 | 252 | PASS |
| all_day_1m_signed_30bar_reversion_1530 | 1m | signed | 30 | 1.75 | 0.10 | 246.98 | 240.69 | 252 | PASS |
| all_day_1m_signed_30bar_reversion_1530 | 1m | signed | 30 | 2.00 | 0.00 | 246.98 | 240.69 | 252 | PASS |
| all_day_1m_signed_30bar_reversion_1530 | 1m | signed | 30 | 2.00 | 0.05 | 246.98 | 240.69 | 252 | PASS |
| all_day_1m_signed_30bar_reversion_1530 | 1m | signed | 30 | 2.00 | 0.10 | 246.98 | 240.69 | 252 | PASS |
| late_morning_5m_large10_12bar_reversion_1230 | 5m | large10 | 12 | 1.00 | 0.00 | 246.72 | 240.69 | 252 | PASS |
| late_morning_5m_large10_12bar_reversion_1230 | 5m | large10 | 12 | 1.00 | 0.05 | 246.65 | 240.69 | 252 | PASS |
| late_morning_5m_large10_12bar_reversion_1230 | 5m | large10 | 12 | 1.00 | 0.10 | 246.52 | 240.69 | 252 | PASS |
| late_morning_5m_large10_12bar_reversion_1230 | 5m | large10 | 12 | 1.25 | 0.00 | 246.20 | 240.69 | 251 | PASS |
| late_morning_5m_large10_12bar_reversion_1230 | 5m | large10 | 12 | 1.25 | 0.05 | 245.87 | 240.69 | 251 | PASS |
| late_morning_5m_large10_12bar_reversion_1230 | 5m | large10 | 12 | 1.25 | 0.10 | 245.62 | 240.69 | 251 | PASS |
| late_morning_5m_large10_12bar_reversion_1230 | 5m | large10 | 12 | 1.50 | 0.00 | 244.39 | 238.09 | 248 | PASS |
| late_morning_5m_large10_12bar_reversion_1230 | 5m | large10 | 12 | 1.50 | 0.05 | 243.61 | 238.09 | 247 | PASS |
| late_morning_5m_large10_12bar_reversion_1230 | 5m | large10 | 12 | 1.50 | 0.10 | 242.64 | 237.44 | 247 | PASS |
| midday_5m_signed_18bar_reversion_1400 | 5m | signed | 18 | 1.00 | 0.00 | 246.98 | 240.69 | 252 | PASS |
| midday_5m_signed_18bar_reversion_1400 | 5m | signed | 18 | 1.00 | 0.02 | 246.98 | 240.69 | 252 | PASS |
| midday_5m_signed_18bar_reversion_1400 | 5m | signed | 18 | 1.00 | 0.05 | 246.78 | 240.69 | 251 | PASS |
| midday_5m_signed_18bar_reversion_1400 | 5m | signed | 18 | 1.25 | 0.00 | 246.98 | 240.69 | 252 | PASS |
| midday_5m_signed_18bar_reversion_1400 | 5m | signed | 18 | 1.25 | 0.02 | 246.98 | 240.69 | 252 | PASS |
| midday_5m_signed_18bar_reversion_1400 | 5m | signed | 18 | 1.25 | 0.05 | 246.65 | 240.69 | 250 | PASS |
| midday_5m_signed_18bar_reversion_1400 | 5m | signed | 18 | 1.50 | 0.00 | 246.85 | 240.69 | 252 | PASS |
| midday_5m_signed_18bar_reversion_1400 | 5m | signed | 18 | 1.50 | 0.02 | 246.78 | 240.69 | 252 | PASS |
| midday_5m_signed_18bar_reversion_1400 | 5m | signed | 18 | 1.50 | 0.05 | 245.75 | 240.69 | 249 | PASS |
| morning_5m_signed_6bar_reversion_1130 | 5m | signed | 6 | 1.00 | 0.00 | 246.98 | 240.69 | 252 | PASS |
| morning_5m_signed_6bar_reversion_1130 | 5m | signed | 6 | 1.00 | 0.02 | 246.98 | 240.69 | 252 | PASS |
| morning_5m_signed_6bar_reversion_1130 | 5m | signed | 6 | 1.00 | 0.05 | 245.94 | 240.69 | 251 | PASS |
| morning_5m_signed_6bar_reversion_1130 | 5m | signed | 6 | 1.25 | 0.00 | 246.98 | 240.69 | 252 | PASS |
| morning_5m_signed_6bar_reversion_1130 | 5m | signed | 6 | 1.25 | 0.02 | 246.98 | 240.69 | 252 | PASS |
| morning_5m_signed_6bar_reversion_1130 | 5m | signed | 6 | 1.25 | 0.05 | 245.55 | 240.69 | 250 | PASS |
| morning_5m_signed_6bar_reversion_1130 | 5m | signed | 6 | 1.50 | 0.00 | 246.98 | 240.69 | 252 | PASS |
| morning_5m_signed_6bar_reversion_1130 | 5m | signed | 6 | 1.50 | 0.02 | 246.85 | 240.69 | 252 | PASS |
| morning_5m_signed_6bar_reversion_1130 | 5m | signed | 6 | 1.50 | 0.05 | 245.10 | 240.69 | 248 | PASS |

Decision: PASS. 45/45 declared entry rows cleared the full-history, limited-core, and latest-window density gates.

Minimum full-history density: 234.54 signals/year. Minimum limited-core density: 236.15 signals/year. Minimum latest-window count: 233.

No return, PnL, trade outcome, stop, target, equity, WFA, Monte Carlo, or holdout data was inspected during this screen.

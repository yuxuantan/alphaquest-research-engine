# NQ Orderflow-Impulse Reversal Density Audit

Generated on 2026-06-30 before any NQ PnL testing for `nq_orderflow_impulse_reversal`.

Input: completed 1-minute NQ RTH bars from `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet` enriched with `propstack.data.features.add_trade_orderflow_features`.

Availability rule: same-clock signed-flow ranks use prior same-clock observations only; rolling signed-flow and return use completed 1-minute bars ending at the signal bar close. The configured entry time is one minute after the signal bar timestamp, so the staged engine can only enter on the next bar open or later.

Full window: 2011-01-03 to 2026-06-12, 3813 sessions, 15.44 calendar years.
Limited-core density proxy window: 2011-02-22 to 2012-09-07, 371 sessions, 1.54 calendar years.
Latest window: 2025-06-09 to 2026-06-12, 252 sessions.

Gate: each declared entry row must produce at least 50 signals/year in full history, at least 50 signals/year in the limited-core window, and at least 50 signals in the latest 252 sessions before any PnL is inspected.

## Variant Summary

| Variant | Entry combos | Passing rows | Min full/year | Min limited/year | Min latest signals | Decision |
|---|---:|---:|---:|---:|---:|---|
| afternoon_60m_impulse_reversal_1400 | 9 | 9 | 84.79 | 71.36 | 88 | PASS |
| early_5m_impulse_reversal_1000 | 9 | 9 | 72.87 | 53.20 | 83 | PASS |
| late_day_30m_impulse_reversal_1500 | 9 | 9 | 69.82 | 63.58 | 75 | PASS |
| late_morning_15m_impulse_reversal_1130 | 9 | 9 | 70.93 | 55.79 | 78 | PASS |
| midday_30m_impulse_reversal_1230 | 9 | 9 | 71.44 | 61.63 | 74 | PASS |

## Entry Rows

| Variant | Pressure rank column | Return column | Rank threshold | Min return ticks | Full/year | Limited/year | Latest signals | Decision |
|---|---|---|---:|---:|---:|---:|---:|---|
| afternoon_60m_impulse_reversal_1400 | trade_orderflow_imbalance_60_rank42 | trade_orderflow_return_ticks_60 | 0.70 | 4 | 123.71 | 107.69 | 121 | PASS |
| afternoon_60m_impulse_reversal_1400 | trade_orderflow_imbalance_60_rank42 | trade_orderflow_return_ticks_60 | 0.70 | 6 | 120.54 | 101.85 | 120 | PASS |
| afternoon_60m_impulse_reversal_1400 | trade_orderflow_imbalance_60_rank42 | trade_orderflow_return_ticks_60 | 0.70 | 8 | 117.56 | 96.02 | 120 | PASS |
| afternoon_60m_impulse_reversal_1400 | trade_orderflow_imbalance_60_rank42 | trade_orderflow_return_ticks_60 | 0.75 | 4 | 106.74 | 92.77 | 104 | PASS |
| afternoon_60m_impulse_reversal_1400 | trade_orderflow_imbalance_60_rank42 | trade_orderflow_return_ticks_60 | 0.75 | 6 | 103.96 | 87.58 | 103 | PASS |
| afternoon_60m_impulse_reversal_1400 | trade_orderflow_imbalance_60_rank42 | trade_orderflow_return_ticks_60 | 0.75 | 8 | 101.50 | 83.69 | 103 | PASS |
| afternoon_60m_impulse_reversal_1400 | trade_orderflow_imbalance_60_rank42 | trade_orderflow_return_ticks_60 | 0.80 | 4 | 88.28 | 77.85 | 88 | PASS |
| afternoon_60m_impulse_reversal_1400 | trade_orderflow_imbalance_60_rank42 | trade_orderflow_return_ticks_60 | 0.80 | 6 | 86.28 | 73.96 | 88 | PASS |
| afternoon_60m_impulse_reversal_1400 | trade_orderflow_imbalance_60_rank42 | trade_orderflow_return_ticks_60 | 0.80 | 8 | 84.79 | 71.36 | 88 | PASS |
| early_5m_impulse_reversal_1000 | trade_orderflow_imbalance_5_rank42 | trade_orderflow_return_ticks_5 | 0.75 | 1 | 115.42 | 100.56 | 119 | PASS |
| early_5m_impulse_reversal_1000 | trade_orderflow_imbalance_5_rank42 | trade_orderflow_return_ticks_5 | 0.75 | 2 | 113.48 | 94.72 | 117 | PASS |
| early_5m_impulse_reversal_1000 | trade_orderflow_imbalance_5_rank42 | trade_orderflow_return_ticks_5 | 0.75 | 3 | 111.67 | 87.58 | 117 | PASS |
| early_5m_impulse_reversal_1000 | trade_orderflow_imbalance_5_rank42 | trade_orderflow_return_ticks_5 | 0.80 | 1 | 94.96 | 80.45 | 103 | PASS |
| early_5m_impulse_reversal_1000 | trade_orderflow_imbalance_5_rank42 | trade_orderflow_return_ticks_5 | 0.80 | 2 | 93.27 | 75.26 | 101 | PASS |
| early_5m_impulse_reversal_1000 | trade_orderflow_imbalance_5_rank42 | trade_orderflow_return_ticks_5 | 0.80 | 3 | 92.04 | 69.42 | 101 | PASS |
| early_5m_impulse_reversal_1000 | trade_orderflow_imbalance_5_rank42 | trade_orderflow_return_ticks_5 | 0.85 | 1 | 75.01 | 61.63 | 84 | PASS |
| early_5m_impulse_reversal_1000 | trade_orderflow_imbalance_5_rank42 | trade_orderflow_return_ticks_5 | 0.85 | 2 | 73.84 | 57.74 | 83 | PASS |
| early_5m_impulse_reversal_1000 | trade_orderflow_imbalance_5_rank42 | trade_orderflow_return_ticks_5 | 0.85 | 3 | 72.87 | 53.20 | 83 | PASS |
| late_day_30m_impulse_reversal_1500 | trade_orderflow_imbalance_30_rank42 | trade_orderflow_return_ticks_30 | 0.75 | 3 | 109.21 | 107.69 | 116 | PASS |
| late_day_30m_impulse_reversal_1500 | trade_orderflow_imbalance_30_rank42 | trade_orderflow_return_ticks_30 | 0.75 | 4 | 107.78 | 106.40 | 115 | PASS |
| late_day_30m_impulse_reversal_1500 | trade_orderflow_imbalance_30_rank42 | trade_orderflow_return_ticks_30 | 0.75 | 5 | 106.61 | 104.45 | 115 | PASS |
| late_day_30m_impulse_reversal_1500 | trade_orderflow_imbalance_30_rank42 | trade_orderflow_return_ticks_30 | 0.80 | 3 | 90.16 | 90.18 | 98 | PASS |
| late_day_30m_impulse_reversal_1500 | trade_orderflow_imbalance_30_rank42 | trade_orderflow_return_ticks_30 | 0.80 | 4 | 88.93 | 88.88 | 97 | PASS |
| late_day_30m_impulse_reversal_1500 | trade_orderflow_imbalance_30_rank42 | trade_orderflow_return_ticks_30 | 0.80 | 5 | 88.03 | 87.58 | 97 | PASS |
| late_day_30m_impulse_reversal_1500 | trade_orderflow_imbalance_30_rank42 | trade_orderflow_return_ticks_30 | 0.85 | 3 | 71.25 | 65.52 | 76 | PASS |
| late_day_30m_impulse_reversal_1500 | trade_orderflow_imbalance_30_rank42 | trade_orderflow_return_ticks_30 | 0.85 | 4 | 70.41 | 64.23 | 75 | PASS |
| late_day_30m_impulse_reversal_1500 | trade_orderflow_imbalance_30_rank42 | trade_orderflow_return_ticks_30 | 0.85 | 5 | 69.82 | 63.58 | 75 | PASS |
| late_morning_15m_impulse_reversal_1130 | trade_orderflow_imbalance_15_rank42 | trade_orderflow_return_ticks_15 | 0.75 | 2 | 110.31 | 91.47 | 117 | PASS |
| late_morning_15m_impulse_reversal_1130 | trade_orderflow_imbalance_15_rank42 | trade_orderflow_return_ticks_15 | 0.75 | 3 | 109.08 | 89.53 | 117 | PASS |
| late_morning_15m_impulse_reversal_1130 | trade_orderflow_imbalance_15_rank42 | trade_orderflow_return_ticks_15 | 0.75 | 4 | 107.65 | 88.23 | 117 | PASS |
| late_morning_15m_impulse_reversal_1130 | trade_orderflow_imbalance_15_rank42 | trade_orderflow_return_ticks_15 | 0.80 | 2 | 90.88 | 71.36 | 96 | PASS |
| late_morning_15m_impulse_reversal_1130 | trade_orderflow_imbalance_15_rank42 | trade_orderflow_return_ticks_15 | 0.80 | 3 | 89.90 | 70.07 | 96 | PASS |
| late_morning_15m_impulse_reversal_1130 | trade_orderflow_imbalance_15_rank42 | trade_orderflow_return_ticks_15 | 0.80 | 4 | 88.80 | 68.77 | 96 | PASS |
| late_morning_15m_impulse_reversal_1130 | trade_orderflow_imbalance_15_rank42 | trade_orderflow_return_ticks_15 | 0.85 | 2 | 72.61 | 57.74 | 78 | PASS |
| late_morning_15m_impulse_reversal_1130 | trade_orderflow_imbalance_15_rank42 | trade_orderflow_return_ticks_15 | 0.85 | 3 | 71.77 | 56.44 | 78 | PASS |
| late_morning_15m_impulse_reversal_1130 | trade_orderflow_imbalance_15_rank42 | trade_orderflow_return_ticks_15 | 0.85 | 4 | 70.93 | 55.79 | 78 | PASS |
| midday_30m_impulse_reversal_1230 | trade_orderflow_imbalance_30_rank42 | trade_orderflow_return_ticks_30 | 0.75 | 2 | 109.92 | 97.31 | 117 | PASS |
| midday_30m_impulse_reversal_1230 | trade_orderflow_imbalance_30_rank42 | trade_orderflow_return_ticks_30 | 0.75 | 3 | 108.75 | 94.07 | 117 | PASS |
| midday_30m_impulse_reversal_1230 | trade_orderflow_imbalance_30_rank42 | trade_orderflow_return_ticks_30 | 0.75 | 4 | 107.07 | 90.83 | 117 | PASS |
| midday_30m_impulse_reversal_1230 | trade_orderflow_imbalance_30_rank42 | trade_orderflow_return_ticks_30 | 0.80 | 2 | 93.98 | 83.04 | 97 | PASS |
| midday_30m_impulse_reversal_1230 | trade_orderflow_imbalance_30_rank42 | trade_orderflow_return_ticks_30 | 0.80 | 3 | 93.14 | 80.45 | 97 | PASS |
| midday_30m_impulse_reversal_1230 | trade_orderflow_imbalance_30_rank42 | trade_orderflow_return_ticks_30 | 0.80 | 4 | 91.65 | 77.20 | 97 | PASS |
| midday_30m_impulse_reversal_1230 | trade_orderflow_imbalance_30_rank42 | trade_orderflow_return_ticks_30 | 0.85 | 2 | 73.13 | 66.17 | 74 | PASS |
| midday_30m_impulse_reversal_1230 | trade_orderflow_imbalance_30_rank42 | trade_orderflow_return_ticks_30 | 0.85 | 3 | 72.48 | 64.88 | 74 | PASS |
| midday_30m_impulse_reversal_1230 | trade_orderflow_imbalance_30_rank42 | trade_orderflow_return_ticks_30 | 0.85 | 4 | 71.44 | 61.63 | 74 | PASS |

Decision: PASS. 45/45 declared entry rows cleared the full-history, limited-core, and latest-window density gates.

Minimum full-history density: 69.82 signals/year. Minimum limited-core density: 53.20 signals/year. Minimum latest-window count: 74.

No return, PnL, trade outcome, stop, target, equity, WFA, Monte Carlo, or holdout data was inspected during this screen.

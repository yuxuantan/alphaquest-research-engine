# NQ Signed Orderflow Persistence Density Audit

Generated on 2026-06-30 before any NQ PnL testing for `nq_signed_orderflow_persistence`.

Input: completed 1-minute NQ RTH bars from `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet` enriched with `propstack.data.features.add_trade_orderflow_features`.

Availability rule: rolling signed-flow imbalance and rolling return use only completed bars ending at the signal bar close. The configured entry time is one minute after the signal bar timestamp, so the staged engine can only enter on the next bar open or later.

Full window: 2011-01-03 to 2026-06-12, 3813 sessions, 15.44 calendar years.
Limited-core density proxy window: 2011-02-22 to 2012-09-07, 371 sessions, 1.54 calendar years.
Latest window: 2025-06-09 to 2026-06-12, 252 sessions.

| Variant | Flow column | Return column | Flow threshold | Min return ticks | Full/year | Limited/year | Latest signals | Decision |
|---|---|---|---:|---:|---:|---:|---:|---|
| afternoon_60m_signed_flow_continuation_1400 | trade_orderflow_imbalance_60 | trade_orderflow_return_ticks_60 | 0.02 | 8 | 104.80 | 112.88 | 74 | PASS |
| afternoon_60m_signed_flow_continuation_1400 | trade_orderflow_imbalance_60 | trade_orderflow_return_ticks_60 | 0.02 | 12 | 98.39 | 100.56 | 74 | PASS |
| afternoon_60m_signed_flow_continuation_1400 | trade_orderflow_imbalance_60 | trade_orderflow_return_ticks_60 | 0.02 | 16 | 91.46 | 84.34 | 73 | PASS |
| afternoon_60m_signed_flow_continuation_1400 | trade_orderflow_imbalance_60 | trade_orderflow_return_ticks_60 | 0.035 | 8 | 63.35 | 94.72 | 25 | FAIL |
| afternoon_60m_signed_flow_continuation_1400 | trade_orderflow_imbalance_60 | trade_orderflow_return_ticks_60 | 0.035 | 12 | 58.62 | 85.64 | 25 | FAIL |
| afternoon_60m_signed_flow_continuation_1400 | trade_orderflow_imbalance_60 | trade_orderflow_return_ticks_60 | 0.035 | 16 | 54.34 | 74.61 | 25 | FAIL |
| afternoon_60m_signed_flow_continuation_1400 | trade_orderflow_imbalance_60 | trade_orderflow_return_ticks_60 | 0.05 | 8 | 38.99 | 79.15 | 7 | FAIL |
| afternoon_60m_signed_flow_continuation_1400 | trade_orderflow_imbalance_60 | trade_orderflow_return_ticks_60 | 0.05 | 12 | 36.14 | 71.36 | 7 | FAIL |
| afternoon_60m_signed_flow_continuation_1400 | trade_orderflow_imbalance_60 | trade_orderflow_return_ticks_60 | 0.05 | 16 | 32.77 | 62.28 | 7 | FAIL |
| early_5m_signed_flow_continuation_1000 | trade_orderflow_imbalance_5 | trade_orderflow_return_ticks_5 | 0.04 | 2 | 126.18 | 121.97 | 104 | PASS |
| early_5m_signed_flow_continuation_1000 | trade_orderflow_imbalance_5 | trade_orderflow_return_ticks_5 | 0.04 | 4 | 119.31 | 107.04 | 104 | PASS |
| early_5m_signed_flow_continuation_1000 | trade_orderflow_imbalance_5 | trade_orderflow_return_ticks_5 | 0.04 | 6 | 111.86 | 90.18 | 104 | PASS |
| early_5m_signed_flow_continuation_1000 | trade_orderflow_imbalance_5 | trade_orderflow_return_ticks_5 | 0.06 | 2 | 93.73 | 103.15 | 68 | PASS |
| early_5m_signed_flow_continuation_1000 | trade_orderflow_imbalance_5 | trade_orderflow_return_ticks_5 | 0.06 | 4 | 89.19 | 92.12 | 68 | PASS |
| early_5m_signed_flow_continuation_1000 | trade_orderflow_imbalance_5 | trade_orderflow_return_ticks_5 | 0.06 | 6 | 84.27 | 80.45 | 68 | PASS |
| early_5m_signed_flow_continuation_1000 | trade_orderflow_imbalance_5 | trade_orderflow_return_ticks_5 | 0.08 | 2 | 67.62 | 82.39 | 40 | FAIL |
| early_5m_signed_flow_continuation_1000 | trade_orderflow_imbalance_5 | trade_orderflow_return_ticks_5 | 0.08 | 4 | 64.32 | 73.96 | 40 | FAIL |
| early_5m_signed_flow_continuation_1000 | trade_orderflow_imbalance_5 | trade_orderflow_return_ticks_5 | 0.08 | 6 | 60.95 | 66.17 | 40 | FAIL |
| late_large20_30m_flow_continuation_1500 | trade_orderflow_large20_imbalance_30 | trade_orderflow_return_ticks_30 | 0.05 | 6 | 95.22 | 71.36 | 103 | PASS |
| late_large20_30m_flow_continuation_1500 | trade_orderflow_large20_imbalance_30 | trade_orderflow_return_ticks_30 | 0.05 | 10 | 84.40 | 57.09 | 101 | PASS |
| late_large20_30m_flow_continuation_1500 | trade_orderflow_large20_imbalance_30 | trade_orderflow_return_ticks_30 | 0.05 | 14 | 75.20 | 43.47 | 99 | FAIL |
| late_large20_30m_flow_continuation_1500 | trade_orderflow_large20_imbalance_30 | trade_orderflow_return_ticks_30 | 0.1 | 6 | 87.83 | 65.52 | 99 | PASS |
| late_large20_30m_flow_continuation_1500 | trade_orderflow_large20_imbalance_30 | trade_orderflow_return_ticks_30 | 0.1 | 10 | 78.05 | 53.20 | 97 | PASS |
| late_large20_30m_flow_continuation_1500 | trade_orderflow_large20_imbalance_30 | trade_orderflow_return_ticks_30 | 0.1 | 14 | 69.31 | 40.22 | 95 | FAIL |
| late_large20_30m_flow_continuation_1500 | trade_orderflow_large20_imbalance_30 | trade_orderflow_return_ticks_30 | 0.15 | 6 | 80.38 | 59.69 | 91 | PASS |
| late_large20_30m_flow_continuation_1500 | trade_orderflow_large20_imbalance_30 | trade_orderflow_return_ticks_30 | 0.15 | 10 | 71.12 | 48.66 | 89 | FAIL |
| late_large20_30m_flow_continuation_1500 | trade_orderflow_large20_imbalance_30 | trade_orderflow_return_ticks_30 | 0.15 | 14 | 63.41 | 38.28 | 87 | FAIL |
| late_morning_15m_signed_flow_continuation_1130 | trade_orderflow_imbalance_15 | trade_orderflow_return_ticks_15 | 0.03 | 4 | 116.07 | 121.32 | 97 | PASS |
| late_morning_15m_signed_flow_continuation_1130 | trade_orderflow_imbalance_15 | trade_orderflow_return_ticks_15 | 0.03 | 8 | 105.77 | 95.37 | 96 | PASS |
| late_morning_15m_signed_flow_continuation_1130 | trade_orderflow_imbalance_15 | trade_orderflow_return_ticks_15 | 0.03 | 12 | 95.09 | 69.42 | 96 | PASS |
| late_morning_15m_signed_flow_continuation_1130 | trade_orderflow_imbalance_15 | trade_orderflow_return_ticks_15 | 0.05 | 4 | 76.63 | 98.61 | 41 | FAIL |
| late_morning_15m_signed_flow_continuation_1130 | trade_orderflow_imbalance_15 | trade_orderflow_return_ticks_15 | 0.05 | 8 | 69.11 | 79.15 | 41 | FAIL |
| late_morning_15m_signed_flow_continuation_1130 | trade_orderflow_imbalance_15 | trade_orderflow_return_ticks_15 | 0.05 | 12 | 61.60 | 59.04 | 41 | FAIL |
| late_morning_15m_signed_flow_continuation_1130 | trade_orderflow_imbalance_15 | trade_orderflow_return_ticks_15 | 0.07 | 4 | 47.02 | 73.31 | 14 | FAIL |
| late_morning_15m_signed_flow_continuation_1130 | trade_orderflow_imbalance_15 | trade_orderflow_return_ticks_15 | 0.07 | 8 | 42.43 | 61.63 | 14 | FAIL |
| late_morning_15m_signed_flow_continuation_1130 | trade_orderflow_imbalance_15 | trade_orderflow_return_ticks_15 | 0.07 | 12 | 37.11 | 46.06 | 14 | FAIL |
| midday_30m_signed_flow_continuation_1230 | trade_orderflow_imbalance_30 | trade_orderflow_return_ticks_30 | 0.025 | 6 | 111.86 | 110.94 | 80 | PASS |
| midday_30m_signed_flow_continuation_1230 | trade_orderflow_imbalance_30 | trade_orderflow_return_ticks_30 | 0.025 | 10 | 101.37 | 88.23 | 80 | PASS |
| midday_30m_signed_flow_continuation_1230 | trade_orderflow_imbalance_30 | trade_orderflow_return_ticks_30 | 0.025 | 14 | 92.82 | 66.82 | 80 | PASS |
| midday_30m_signed_flow_continuation_1230 | trade_orderflow_imbalance_30 | trade_orderflow_return_ticks_30 | 0.04 | 6 | 76.56 | 94.07 | 42 | FAIL |
| midday_30m_signed_flow_continuation_1230 | trade_orderflow_imbalance_30 | trade_orderflow_return_ticks_30 | 0.04 | 10 | 68.85 | 73.96 | 42 | FAIL |
| midday_30m_signed_flow_continuation_1230 | trade_orderflow_imbalance_30 | trade_orderflow_return_ticks_30 | 0.04 | 14 | 62.44 | 58.39 | 42 | FAIL |
| midday_30m_signed_flow_continuation_1230 | trade_orderflow_imbalance_30 | trade_orderflow_return_ticks_30 | 0.06 | 6 | 44.50 | 76.55 | 8 | FAIL |
| midday_30m_signed_flow_continuation_1230 | trade_orderflow_imbalance_30 | trade_orderflow_return_ticks_30 | 0.06 | 10 | 39.38 | 61.63 | 8 | FAIL |
| midday_30m_signed_flow_continuation_1230 | trade_orderflow_imbalance_30 | trade_orderflow_return_ticks_30 | 0.06 | 14 | 34.85 | 48.66 | 8 | FAIL |

Decision: FAIL. 20/45 declared entry rows cleared the full-history, limited-core, and latest-window density gates.

Minimum full-history density: 32.77 signals/year. Minimum limited-core density: 38.28 signals/year. Minimum latest-window count: 7.

No return, PnL, trade outcome, stop, target, equity, WFA, Monte Carlo, or holdout data was inspected during this screen.

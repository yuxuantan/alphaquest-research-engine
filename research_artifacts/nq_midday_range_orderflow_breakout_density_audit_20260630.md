# NQ Midday Range Orderflow Breakout Density Audit

Generated on 2026-06-30 before any NQ PnL testing for `nq_midday_range_orderflow_breakout`.

Input: completed 5-minute NQ RTH bars from `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet` via `propstack.data.pipeline.prepare_data`.

Availability rule: the lunch/late-lunch range is frozen only after its configured window closes; breakout and orderflow confirmation use completed post-range bars; no PnL, future high/low, final VWAP, or future orderflow is used.

Full window: 2011-01-03 to 2026-06-12, 3813 sessions.
Limited-core density window: 2011-02-22 to 2012-09-07, 371 sessions.
Latest window: 2025-06-09 to 2026-06-12, 252 sessions.

| Variant | Flow | Max range | Min imbalance | Full/year | Limited/year | Latest signals | Decision |
|---|---|---:|---:|---:|---:|---:|---|
| late_lunch_1200_1330_large10_breakout_1500 | large10 | 80 | 0.0 | 136.45 | 179.39 | 57 | PASS |
| late_lunch_1200_1330_large10_breakout_1500 | large10 | 80 | 0.05 | 134.96 | 178.74 | 56 | PASS |
| late_lunch_1200_1330_large10_breakout_1500 | large10 | 80 | 0.1 | 133.28 | 175.50 | 55 | PASS |
| late_lunch_1200_1330_large10_breakout_1500 | large10 | 100 | 0.0 | 149.47 | 179.39 | 83 | PASS |
| late_lunch_1200_1330_large10_breakout_1500 | large10 | 100 | 0.05 | 147.85 | 178.74 | 82 | PASS |
| late_lunch_1200_1330_large10_breakout_1500 | large10 | 100 | 0.1 | 146.04 | 175.50 | 81 | PASS |
| late_lunch_1200_1330_large10_breakout_1500 | large10 | 120 | 0.0 | 157.43 | 179.39 | 102 | PASS |
| late_lunch_1200_1330_large10_breakout_1500 | large10 | 120 | 0.05 | 155.75 | 178.74 | 101 | PASS |
| late_lunch_1200_1330_large10_breakout_1500 | large10 | 120 | 0.1 | 153.81 | 175.50 | 100 | PASS |
| late_lunch_1200_1330_signed_breakout_1500 | signed_volume | 80 | 0.0 | 145.78 | 187.16 | 60 | PASS |
| late_lunch_1200_1330_signed_breakout_1500 | signed_volume | 80 | 0.03 | 143.25 | 185.86 | 57 | PASS |
| late_lunch_1200_1330_signed_breakout_1500 | signed_volume | 80 | 0.06 | 139.82 | 184.57 | 52 | PASS |
| late_lunch_1200_1330_signed_breakout_1500 | signed_volume | 100 | 0.0 | 159.12 | 187.16 | 87 | PASS |
| late_lunch_1200_1330_signed_breakout_1500 | signed_volume | 100 | 0.03 | 156.53 | 185.86 | 83 | PASS |
| late_lunch_1200_1330_signed_breakout_1500 | signed_volume | 100 | 0.06 | 151.99 | 184.57 | 76 | PASS |
| late_lunch_1200_1330_signed_breakout_1500 | signed_volume | 120 | 0.0 | 167.79 | 187.16 | 109 | PASS |
| late_lunch_1200_1330_signed_breakout_1500 | signed_volume | 120 | 0.03 | 164.69 | 185.86 | 103 | PASS |
| late_lunch_1200_1330_signed_breakout_1500 | signed_volume | 120 | 0.06 | 159.18 | 184.57 | 91 | PASS |
| lunch_1130_1300_large10_breakout_1430 | large10 | 80 | 0.0 | 124.92 | 161.90 | 48 | PASS |
| lunch_1130_1300_large10_breakout_1430 | large10 | 80 | 0.05 | 122.98 | 159.96 | 48 | PASS |
| lunch_1130_1300_large10_breakout_1430 | large10 | 80 | 0.1 | 122.07 | 156.72 | 47 | PASS |
| lunch_1130_1300_large10_breakout_1430 | large10 | 100 | 0.0 | 139.17 | 161.90 | 83 | PASS |
| lunch_1130_1300_large10_breakout_1430 | large10 | 100 | 0.05 | 136.84 | 159.96 | 81 | PASS |
| lunch_1130_1300_large10_breakout_1430 | large10 | 100 | 0.1 | 135.87 | 156.72 | 80 | PASS |
| lunch_1130_1300_large10_breakout_1430 | large10 | 120 | 0.0 | 147.72 | 161.90 | 100 | PASS |
| lunch_1130_1300_large10_breakout_1430 | large10 | 120 | 0.05 | 145.39 | 159.96 | 98 | PASS |
| lunch_1130_1300_large10_breakout_1430 | large10 | 120 | 0.1 | 144.29 | 156.72 | 97 | PASS |
| lunch_1130_1300_large20_breakout_1430 | large20 | 80 | 0.0 | 112.23 | 154.78 | 39 | PASS |
| lunch_1130_1300_large20_breakout_1430 | large20 | 80 | 0.05 | 111.13 | 152.84 | 39 | PASS |
| lunch_1130_1300_large20_breakout_1430 | large20 | 80 | 0.1 | 110.35 | 152.84 | 38 | PASS |
| lunch_1130_1300_large20_breakout_1430 | large20 | 100 | 0.0 | 124.08 | 154.78 | 66 | PASS |
| lunch_1130_1300_large20_breakout_1430 | large20 | 100 | 0.05 | 122.72 | 152.84 | 65 | PASS |
| lunch_1130_1300_large20_breakout_1430 | large20 | 100 | 0.1 | 121.88 | 152.84 | 64 | PASS |
| lunch_1130_1300_large20_breakout_1430 | large20 | 120 | 0.0 | 130.95 | 154.78 | 81 | PASS |
| lunch_1130_1300_large20_breakout_1430 | large20 | 120 | 0.05 | 129.52 | 152.84 | 80 | PASS |
| lunch_1130_1300_large20_breakout_1430 | large20 | 120 | 0.1 | 128.61 | 152.84 | 79 | PASS |
| lunch_1130_1300_signed_breakout_1430 | signed_volume | 80 | 0.0 | 133.80 | 169.03 | 50 | PASS |
| lunch_1130_1300_signed_breakout_1430 | signed_volume | 80 | 0.03 | 132.37 | 167.08 | 49 | PASS |
| lunch_1130_1300_signed_breakout_1430 | signed_volume | 80 | 0.06 | 127.97 | 164.49 | 46 | PASS |
| lunch_1130_1300_signed_breakout_1430 | signed_volume | 100 | 0.0 | 149.01 | 169.03 | 85 | PASS |
| lunch_1130_1300_signed_breakout_1430 | signed_volume | 100 | 0.03 | 147.27 | 167.08 | 83 | PASS |
| lunch_1130_1300_signed_breakout_1430 | signed_volume | 100 | 0.06 | 141.89 | 164.49 | 74 | PASS |
| lunch_1130_1300_signed_breakout_1430 | signed_volume | 120 | 0.0 | 158.40 | 169.03 | 105 | PASS |
| lunch_1130_1300_signed_breakout_1430 | signed_volume | 120 | 0.03 | 156.33 | 167.08 | 102 | PASS |
| lunch_1130_1300_signed_breakout_1430 | signed_volume | 120 | 0.06 | 149.53 | 164.49 | 90 | PASS |

Decision: PASS. 45/45 declared entry rows cleared the full-history, limited-core, and latest-window density gates.

Minimum full-history density: 110.35 signals/year. Minimum limited-core density: 152.84 signals/year. Minimum latest-window count: 38.

No return, PnL, or trade outcome data was inspected during this screen.

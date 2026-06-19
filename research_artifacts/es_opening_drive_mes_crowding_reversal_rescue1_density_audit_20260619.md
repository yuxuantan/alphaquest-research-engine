# ES Opening-Drive MES Crowding Reversal Rescue1 Density Audit

Date: 2026-06-19

Data: `data/cache/orderflow/es_mes_participation_crowding_1m_20190506_20260609_full_rth_ny.csv`

Method: vectorized entry-only signal-count audit over rescue1 declared entry grids. No PnL, stop, target, monkey, WFA, or Monte Carlo result was inspected.

Decision before rescue staged PnL: PASS

| variant | min full signals/year | min limited-core signals/year | min full signals | min limited signals | limited-core period |
|---|---:|---:|---:|---:|---|
| od15_notional_failed_extension_reversal_1130 | 115.27 | 129.74 | 818 | 92 | 2021-07-13 to 2022-03-28 |
| od15_trade_failed_extension_reversal_1130 | 98.64 | 126.92 | 700 | 90 | 2021-07-13 to 2022-03-28 |
| od30_notional_failed_extension_reversal_1300 | 94.27 | 126.92 | 669 | 90 | 2021-07-13 to 2022-03-28 |
| od30_trade_failed_extension_reversal_1300 | 111.18 | 150.89 | 789 | 107 | 2021-07-13 to 2022-03-28 |
| od60_notional_failed_extension_reversal_1530 | 96.39 | 110.00 | 684 | 78 | 2021-07-13 to 2022-03-28 |

CSV: `research_artifacts/es_opening_drive_mes_crowding_reversal_rescue1_density_audit_20260619.csv`

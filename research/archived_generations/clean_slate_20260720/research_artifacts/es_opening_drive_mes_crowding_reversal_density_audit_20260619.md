# ES Opening-Drive MES Crowding Reversal Density Audit

Date: 2026-06-19

Data: `data/cache/orderflow/es_mes_participation_crowding_1m_20190506_20260609_full_rth_ny.csv`
Full configured data: `2019-05-06` through `2026-06-09`.

Method: vectorized reproduction of the entry module signal conditions over the declared entry parameter grid only. It freezes opening-drive metrics by session, applies failed-extension and MES-rank filters, enforces one signal per day, and does not inspect PnL, stops, targets, WFA, monkey, or Monte Carlo results.

Decision before staged PnL: PASS

| variant | min full signals/year | min limited-core signals/year | min full signals | min limited signals | limited-core period |
|---|---:|---:|---:|---:|---|
| od15_notional_failed_extension_reversal_1130 | 99.91 | 114.23 | 709 | 81 | 2021-07-13 to 2022-03-28 |
| od15_trade_failed_extension_reversal_1130 | 99.91 | 118.46 | 709 | 84 | 2021-07-13 to 2022-03-28 |
| od30_notional_failed_extension_reversal_1300 | 100.47 | 128.33 | 713 | 91 | 2021-07-13 to 2022-03-28 |
| od30_trade_failed_extension_reversal_1300 | 100.19 | 138.20 | 711 | 98 | 2021-07-13 to 2022-03-28 |
| od60_notional_failed_extension_reversal_1530 | 102.44 | 108.59 | 727 | 77 | 2021-07-13 to 2022-03-28 |

CSV: `research_artifacts/es_opening_drive_mes_crowding_reversal_density_audit_20260619.csv`

# NQ Opening-Drive MES Crowding Reversal Density Audit

Verdict: APPROVE FOR STAGED PNL.

This pre-PnL audit mirrored the completed-bar predicates in `opening_drive_mes_crowding_reversal` and counted entry-condition signals only. No stop, target, PnL, monkey, WFA, Monte Carlo, prop simulation, or holdout result was inspected.

Full-history subset: `{"end_date": "2026-06-12", "session_labels": ["RTH"], "start_date": "2019-05-06"}`.
Limited-core reference subset: `{"end_date": "2022-03-28", "session_labels": ["RTH"], "start_date": "2021-07-13"}`.

| variant | window | entry combos | min signals/year | max signals/year | weakest entry params | pass |
|---|---|---:|---:|---:|---|---|
| od15_notional_failed_extension_reversal_1130 | full_history | 9 | 100.80 | 131.87 | `{"min_opening_drive_ticks": 6, "share_rank_min": 0.65}` | yes |
| od15_notional_failed_extension_reversal_1130 | limited_core | 9 | 109.01 | 138.74 | `{"min_opening_drive_ticks": 4, "share_rank_min": 0.65}` | yes |
| od15_trade_failed_extension_reversal_1130 | full_history | 9 | 98.08 | 132.01 | `{"min_opening_drive_ticks": 6, "share_rank_min": 0.65}` | yes |
| od15_trade_failed_extension_reversal_1130 | limited_core | 9 | 107.60 | 141.57 | `{"min_opening_drive_ticks": 4, "share_rank_min": 0.65}` | yes |
| od30_notional_failed_extension_reversal_1300 | full_history | 9 | 99.80 | 128.58 | `{"min_opening_drive_ticks": 6, "share_rank_min": 0.65}` | yes |
| od30_notional_failed_extension_reversal_1300 | limited_core | 9 | 106.18 | 142.99 | `{"min_opening_drive_ticks": 2, "share_rank_min": 0.65}` | yes |
| od30_trade_failed_extension_reversal_1300 | full_history | 9 | 94.21 | 127.72 | `{"min_opening_drive_ticks": 6, "share_rank_min": 0.65}` | yes |
| od30_trade_failed_extension_reversal_1300 | limited_core | 9 | 113.26 | 141.57 | `{"min_opening_drive_ticks": 2, "share_rank_min": 0.65}` | yes |
| od60_notional_failed_extension_reversal_1530 | full_history | 9 | 98.94 | 132.59 | `{"min_opening_drive_ticks": 6, "share_rank_min": 0.65}` | yes |
| od60_notional_failed_extension_reversal_1530 | limited_core | 9 | 92.02 | 121.75 | `{"min_opening_drive_ticks": 2, "share_rank_min": 0.65}` | yes |

CSV detail: `research_artifacts/nq_opening_drive_mes_crowding_reversal_density_audit_20260630.csv`

# NQ Sector-Rotation Orderflow Pullback Density Audit

Verdict: REJECT BEFORE PNL.

This pre-PnL audit used the staged data-preparation path and the actual `sector_rotation_orderflow_pullback` entry module to count entry-condition signals only. No stop, target, PnL, monkey, WFA, Monte Carlo, prop simulation, or holdout result was inspected.

Full-history subset: `{"end_date": "2026-06-12", "session_labels": ["RTH"], "start_date": "2011-01-03"}`.
Limited-core reference subset: `{"end_date": "2012-09-07", "session_labels": ["RTH"], "start_date": "2011-02-22"}`.

| variant | window | entry combos | min signals/year | max signals/year | weakest entry params | pass |
|---|---|---:|---:|---:|---|---|
| cyclical_vwap_reclaim_signed_long_1400 | full_history | 9 | 49.10 | 77.46 | `{"min_orderflow_imbalance": 0.06, "rank_threshold": 0.65}` | no |
| cyclical_vwap_reclaim_signed_long_1400 | limited_core | 9 | 57.74 | 79.47 | `{"min_orderflow_imbalance": 0.06, "rank_threshold": 0.65}` | yes |
| defensive_ema_pullback_signed_short_1530 | full_history | 9 | 41.50 | 60.34 | `{"min_orderflow_imbalance": 0.06, "rank_threshold": 0.65}` | no |
| defensive_ema_pullback_signed_short_1530 | limited_core | 9 | 52.30 | 65.89 | `{"min_orderflow_imbalance": 0.06, "rank_threshold": 0.65}` | yes |
| defensive_vwap_reject_large10_short_1130 | full_history | 9 | 40.58 | 52.54 | `{"min_orderflow_imbalance": 0.06, "rank_threshold": 0.65}` | no |
| defensive_vwap_reject_large10_short_1130 | limited_core | 9 | 45.51 | 54.34 | `{"min_orderflow_imbalance": 0.06, "rank_threshold": 0.65}` | no |
| financial_industrial_ema_pullback_large10_long_1500 | full_history | 9 | 41.24 | 55.25 | `{"min_orderflow_imbalance": 0.06, "rank_threshold": 0.65}` | no |
| financial_industrial_ema_pullback_large10_long_1500 | limited_core | 9 | 44.83 | 62.49 | `{"min_orderflow_imbalance": 0.06, "rank_threshold": 0.65}` | no |
| growth_vwap_reclaim_large10_long_1130 | full_history | 9 | 45.21 | 58.75 | `{"min_orderflow_imbalance": 0.06, "rank_threshold": 0.65}` | no |
| growth_vwap_reclaim_large10_long_1130 | limited_core | 9 | 44.15 | 55.70 | `{"min_orderflow_imbalance": 0.06, "rank_threshold": 0.65}` | no |

CSV detail: `research_artifacts/nq_sector_rotation_orderflow_pullback_density_audit_20260630.csv`

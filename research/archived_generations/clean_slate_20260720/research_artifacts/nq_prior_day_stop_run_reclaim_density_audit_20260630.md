# NQ Prior-Day Stop-Run Reclaim Density Audit

Verdict: REJECT BEFORE PNL.

This pre-PnL audit used the actual `pdh_pdl_sweep_reclaim` entry logic and counted entry-condition signals only. No stop, target, PnL, monkey, WFA, Monte Carlo, prop simulation, or holdout result was inspected.

Full-history subset: `{"end_date": "2026-06-12", "session_labels": ["RTH"], "start_date": "2011-01-03"}`.
Limited-core reference subset: `{"end_date": "2012-09-07", "session_labels": ["RTH"], "start_date": "2011-02-22"}`.

| variant | window | entry combos | min signals/year | max signals/year | weakest entry params | pass |
|---|---|---:|---:|---:|---|---|
| full_session_two_sided_reclaim | full_history | 9 | 43.42 | 88.03 | `{"min_volume_ratio": 1.25, "reclaim_window_bars": 1}` | no |
| full_session_two_sided_reclaim | limited_core | 9 | 48.91 | 99.17 | `{"min_volume_ratio": 1.25, "reclaim_window_bars": 1}` | no |
| morning_prior_low_reclaim_long | full_history | 9 | 16.52 | 29.54 | `{"min_volume_ratio": 1.25, "reclaim_window_bars": 1}` | no |
| morning_prior_low_reclaim_long | limited_core | 9 | 17.66 | 34.64 | `{"min_volume_ratio": 1.25, "reclaim_window_bars": 1}` | no |
| morning_prior_high_reject_short | full_history | 9 | 14.34 | 31.33 | `{"min_volume_ratio": 1.25, "reclaim_window_bars": 1}` | no |
| morning_prior_high_reject_short | limited_core | 9 | 14.26 | 29.21 | `{"min_volume_ratio": 1.25, "reclaim_window_bars": 1}` | no |
| midday_two_sided_reclaim | full_history | 9 | 4.49 | 13.75 | `{"min_volume_ratio": 1.25, "reclaim_window_bars": 1}` | no |
| midday_two_sided_reclaim | limited_core | 9 | 6.11 | 19.70 | `{"min_volume_ratio": 1.25, "reclaim_window_bars": 1}` | no |
| afternoon_two_sided_reclaim | full_history | 9 | 8.53 | 13.61 | `{"min_volume_ratio": 1.25, "reclaim_window_bars": 1}` | no |
| afternoon_two_sided_reclaim | limited_core | 9 | 10.87 | 15.62 | `{"min_volume_ratio": 1.25, "reclaim_window_bars": 1}` | no |

CSV detail: `research_artifacts/nq_prior_day_stop_run_reclaim_density_audit_20260630.csv`

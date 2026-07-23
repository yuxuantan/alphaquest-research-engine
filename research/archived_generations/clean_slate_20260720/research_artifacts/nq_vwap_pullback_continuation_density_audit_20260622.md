# NQ VWAP Pullback Continuation Density Audit

Verdict: APPROVED FOR TESTING.

This pre-PnL audit used the actual VWAP pullback entry module with lightweight completed-bar records and counted signal availability only.

Pre-PnL density-only reformulations were preserved in rejected audit artifacts. Final signal grids use `min_drive_points=[2,3,5]`, `required_trend_closes=[2,3]` where applicable, and `failed_break_min_ticks=[0,1,2]` where applicable.

| variant | window | entry combos | min signals/year | max signals/year | weakest entry params |
|---|---|---:|---:|---:|---|
| failed_vwap_break_two_sided | limited_core | 9 | 75.26 | 294.54 | `{"failed_break_min_ticks": 2, "min_drive_points": 5.0}` |
| failed_vwap_break_two_sided | full_history | 9 | 262.59 | 407.09 | `{"failed_break_min_ticks": 2, "min_drive_points": 5.0}` |
| midday_trend_reclaim_two_sided | limited_core | 6 | 60.98 | 151.16 | `{"min_drive_points": 5.0, "required_trend_closes": 3}` |
| midday_trend_reclaim_two_sided | full_history | 6 | 113.68 | 205.13 | `{"min_drive_points": 5.0, "required_trend_closes": 3}` |
| morning_opening_drive_pullback_long | limited_core | 9 | 92.77 | 253.66 | `{"min_drive_points": 5.0, "opening_drive_minutes": 45}` |
| morning_opening_drive_pullback_long | full_history | 9 | 141.46 | 267.70 | `{"min_drive_points": 5.0, "opening_drive_minutes": 45}` |
| morning_opening_drive_pullback_short | limited_core | 9 | 114.83 | 248.47 | `{"min_drive_points": 5.0, "opening_drive_minutes": 45}` |
| morning_opening_drive_pullback_short | full_history | 9 | 137.06 | 267.51 | `{"min_drive_points": 5.0, "opening_drive_minutes": 45}` |
| morning_trend_reclaim_two_sided | limited_core | 6 | 162.19 | 410.66 | `{"min_drive_points": 5.0, "required_trend_closes": 3}` |
| morning_trend_reclaim_two_sided | full_history | 6 | 294.97 | 485.86 | `{"min_drive_points": 5.0, "required_trend_closes": 3}` |

Initial rejected density screen: `research_artifacts/nq_vwap_pullback_continuation_initial_density_rejected_20260622.md`
Reformulation-1 rejected density screen: `research_artifacts/nq_vwap_pullback_continuation_density_reform1_rejected_20260622.md`
CSV detail: `research_artifacts/nq_vwap_pullback_continuation_density_audit_20260622.csv`

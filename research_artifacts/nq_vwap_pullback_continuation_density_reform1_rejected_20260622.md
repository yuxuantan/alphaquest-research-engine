# NQ VWAP Pullback Continuation Density Audit

Verdict: REJECT BEFORE PNL.

This pre-PnL audit used the actual VWAP pullback entry module with lightweight completed-bar records and counted signal availability only. Entry grid dimensions were signal controls only; stop and target grids do not affect density.

The initial density screen rejected only strict entry corners before PnL. The final grid uses `min_drive_points=[3,5,8]`, `required_trend_closes=[2,3]` where applicable, and `failed_break_min_ticks=[1,2,3]` where applicable.

| variant | window | entry combos | min signals/year | max signals/year | weakest entry params |
|---|---|---:|---:|---:|---|
| failed_vwap_break_two_sided | limited_core | 9 | 23.36 | 176.46 | `{"failed_break_min_ticks": 3, "min_drive_points": 8.0}` |
| failed_vwap_break_two_sided | full_history | 9 | 204.49 | 336.30 | `{"failed_break_min_ticks": 3, "min_drive_points": 8.0}` |
| midday_trend_reclaim_two_sided | limited_core | 6 | 29.84 | 121.32 | `{"min_drive_points": 8.0, "required_trend_closes": 3}` |
| midday_trend_reclaim_two_sided | full_history | 6 | 87.51 | 185.90 | `{"min_drive_points": 8.0, "required_trend_closes": 3}` |
| morning_opening_drive_pullback_long | limited_core | 9 | 50.60 | 205.01 | `{"min_drive_points": 8.0, "opening_drive_minutes": 45}` |
| morning_opening_drive_pullback_long | full_history | 9 | 121.58 | 253.26 | `{"min_drive_points": 8.0, "opening_drive_minutes": 45}` |
| morning_opening_drive_pullback_short | limited_core | 9 | 76.55 | 224.47 | `{"min_drive_points": 8.0, "opening_drive_minutes": 45}` |
| morning_opening_drive_pullback_short | full_history | 9 | 119.96 | 255.53 | `{"min_drive_points": 8.0, "opening_drive_minutes": 45}` |
| morning_trend_reclaim_two_sided | limited_core | 6 | 67.47 | 327.62 | `{"min_drive_points": 8.0, "required_trend_closes": 3}` |
| morning_trend_reclaim_two_sided | full_history | 6 | 225.93 | 443.43 | `{"min_drive_points": 8.0, "required_trend_closes": 3}` |

Initial rejected density screen: `research_artifacts/nq_vwap_pullback_continuation_initial_density_rejected_20260622.md`
CSV detail: `research_artifacts/nq_vwap_pullback_continuation_density_audit_20260622.csv`

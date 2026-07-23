# NQ VWAP Pullback Continuation Density Audit

Verdict: REJECT BEFORE PNL.

This pre-PnL audit used the actual VWAP pullback entry module with lightweight completed-bar records and counted signal availability only. Entry grid dimensions were `required_trend_closes` and NQ-scaled `min_drive_points`; stop and target grids do not affect density.

| variant | window | entry combos | min signals/year | max signals/year | weakest entry params |
|---|---|---:|---:|---:|---|
| failed_vwap_break_two_sided | limited_core | 9 | 6.49 | 103.15 | `{"failed_break_min_ticks": 4, "min_drive_points": 14.0}` |
| failed_vwap_break_two_sided | full_history | 9 | 148.07 | 287.33 | `{"failed_break_min_ticks": 4, "min_drive_points": 14.0}` |
| midday_trend_reclaim_two_sided | limited_core | 9 | 0.65 | 84.99 | `{"min_drive_points": 14.0, "required_trend_closes": 4}` |
| midday_trend_reclaim_two_sided | full_history | 9 | 46.57 | 151.70 | `{"min_drive_points": 14.0, "required_trend_closes": 4}` |
| morning_opening_drive_pullback_long | limited_core | 9 | 14.27 | 148.57 | `{"min_drive_points": 14.0, "opening_drive_minutes": 15}` |
| morning_opening_drive_pullback_long | full_history | 9 | 91.26 | 226.57 | `{"min_drive_points": 14.0, "opening_drive_minutes": 45}` |
| morning_opening_drive_pullback_short | limited_core | 9 | 14.27 | 152.46 | `{"min_drive_points": 14.0, "opening_drive_minutes": 15}` |
| morning_opening_drive_pullback_short | full_history | 9 | 93.92 | 225.15 | `{"min_drive_points": 14.0, "opening_drive_minutes": 45}` |
| morning_trend_reclaim_two_sided | limited_core | 9 | 16.22 | 198.52 | `{"min_drive_points": 14.0, "required_trend_closes": 4}` |
| morning_trend_reclaim_two_sided | full_history | 9 | 128.25 | 367.13 | `{"min_drive_points": 14.0, "required_trend_closes": 4}` |

CSV detail: `research_artifacts/nq_vwap_pullback_continuation_density_audit_20260622.csv`

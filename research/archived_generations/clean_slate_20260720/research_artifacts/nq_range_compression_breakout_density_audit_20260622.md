# NQ Range Compression Breakout Density Audit

Verdict: REJECT BEFORE PNL.

This vectorized pre-PnL audit mirrored the entry module rules: completed prior-session compression, optional inside-day requirement, completed opening-range references, completed 5-minute close breakouts, and one signal maximum per day. It counted signal availability only, before NQ PnL inspection.

| variant | window | entry combos | min signals/year | max signals/year | weakest entry params |
|---|---|---:|---:|---:|---|
| id_nr4_prior_session_breakout | limited_core | 9 | 12.33 | 13.62 | `{"max_prior_range_points": 40, "min_breakout_ticks": 0}` |
| id_nr4_prior_session_breakout | full_history | 9 | 5.44 | 9.52 | `{"max_prior_range_points": 40, "min_breakout_ticks": 0}` |
| nr4_prior_session_breakout | limited_core | 9 | 50.60 | 55.79 | `{"max_prior_range_points": 40, "min_breakout_ticks": 4}` |
| nr4_prior_session_breakout | full_history | 9 | 23.06 | 43.14 | `{"max_prior_range_points": 40, "min_breakout_ticks": 4}` |
| nr7_opening_range_15_long_breakout | limited_core | 9 | 22.06 | 25.30 | `{"max_prior_range_points": 40, "min_breakout_ticks": 4}` |
| nr7_opening_range_15_long_breakout | full_history | 9 | 9.97 | 19.11 | `{"max_prior_range_points": 40, "min_breakout_ticks": 4}` |
| nr7_opening_range_15_short_breakout | limited_core | 9 | 16.87 | 23.36 | `{"max_prior_range_points": 40, "min_breakout_ticks": 4}` |
| nr7_opening_range_15_short_breakout | full_history | 9 | 8.36 | 15.80 | `{"max_prior_range_points": 40, "min_breakout_ticks": 4}` |
| nr7_opening_range_30_breakout | limited_core | 9 | 33.09 | 36.33 | `{"max_prior_range_points": 40, "min_breakout_ticks": 4}` |
| nr7_opening_range_30_breakout | full_history | 9 | 15.35 | 28.05 | `{"max_prior_range_points": 40, "min_breakout_ticks": 4}` |

CSV detail: `research_artifacts/nq_range_compression_breakout_density_audit_20260622.csv`

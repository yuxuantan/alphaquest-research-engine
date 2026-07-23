# NQ Prior-Session Level Breakout Continuation Density Audit

Verdict: REJECT BEFORE PNL.

This pre-PnL audit used the actual prior-session high/low breakout entry module with completed-bar records and counted signal availability only.

| variant | window | entry combos | min signals/year | max signals/year | weakest entry params |
|---|---|---:|---:|---:|---|
| gap_hold_two_sided_continuation | limited_core | 9 | 68.77 | 83.69 | `{"gap_hold_bars": 3, "min_gap_points": 2.0}` |
| gap_hold_two_sided_continuation | full_history | 9 | 70.02 | 84.92 | `{"gap_hold_bars": 3, "min_gap_points": 2.0}` |
| midday_two_sided_close_break | limited_core | 9 | 9.73 | 14.92 | `{"close_buffer_ticks": 1, "min_volume_ratio": 1.25}` |
| midday_two_sided_close_break | full_history | 9 | 6.28 | 10.62 | `{"close_buffer_ticks": 2, "min_volume_ratio": 1.25}` |
| morning_prior_high_breakout_long | limited_core | 9 | 12.33 | 20.11 | `{"close_buffer_ticks": 2, "min_volume_ratio": 1.25}` |
| morning_prior_high_breakout_long | full_history | 9 | 13.41 | 20.99 | `{"close_buffer_ticks": 2, "min_volume_ratio": 1.25}` |
| morning_prior_low_breakout_short | limited_core | 9 | 16.87 | 22.06 | `{"close_buffer_ticks": 2, "min_volume_ratio": 1.25}` |
| morning_prior_low_breakout_short | full_history | 9 | 18.52 | 23.90 | `{"close_buffer_ticks": 2, "min_volume_ratio": 1.25}` |
| retest_hold_two_sided_breakout | limited_core | 9 | 17.52 | 36.33 | `{"close_buffer_ticks": 2, "retest_window_bars": 1}` |
| retest_hold_two_sided_breakout | full_history | 9 | 19.89 | 32.39 | `{"close_buffer_ticks": 2, "retest_window_bars": 1}` |

CSV detail: `research_artifacts/nq_prior_session_level_breakout_continuation_density_audit_20260622.csv`

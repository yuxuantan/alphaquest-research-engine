# morning_high_delta_divergence_short

Campaign: `nq_session_extreme_delta_divergence`

Variant expression: Morning fresh-session-high signed-volume non-confirmation short.

Mechanic: From 10:00 through 12:00 ET, short NQ when a completed one-minute bar makes a fresh current-session high by the grid threshold, closes back within eight ticks of the prior completed high, and cumulative signed-volume progress since that prior high is weak. The reference high/low is from completed prior RTH bars only; the signal bar is evaluated after close and the staged engine enters no earlier than the next bar.

Parameter space before testing: `entry.params.min_extreme_break_ticks` in `[1, 2]`, `entry.params.max_delta_progress_ratio` in `[0.05, 0.1]`, `sl.params.stop_pct` in `[0.001, 0.0015, 0.0025]`, and fixed `tp.params.target_r_multiple=1.0` for 12 total combinations.

No NQ rescue attempt is authorized after results.

# afternoon_low_delta_divergence_long

Campaign: `nq_session_extreme_delta_divergence`

Variant expression: Afternoon fresh-session-low signed-volume non-confirmation long.

Mechanic: From 13:00 through 15:15 ET, buy NQ when a completed one-minute bar makes a fresh current-session low by the grid threshold, closes back within eight ticks of the prior completed low, and cumulative signed-volume progress since that prior low is not confirming downside pressure. The reference high/low is from completed prior RTH bars only; the signal bar is evaluated after close and the staged engine enters no earlier than the next bar.

Parameter space before testing: `entry.params.min_extreme_break_ticks` in `[1, 2]`, `entry.params.max_delta_progress_ratio` in `[0.05, 0.1]`, `sl.params.stop_pct` in `[0.001, 0.0015, 0.0025]`, and fixed `tp.params.target_r_multiple=1.0` for 12 total combinations.

No NQ rescue attempt is authorized after results.

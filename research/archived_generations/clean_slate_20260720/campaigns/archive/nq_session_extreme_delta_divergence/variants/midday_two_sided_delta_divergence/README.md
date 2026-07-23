# midday_two_sided_delta_divergence

Campaign: `nq_session_extreme_delta_divergence`

Variant expression: Midday two-sided fresh-session-extreme signed-volume non-confirmation fade.

Mechanic: From 11:00 through 14:00 ET, fade either fresh current-session high or fresh current-session low when the completed-bar extreme is not confirmed by cumulative signed-volume progress from the prior completed extreme. The reference high/low is from completed prior RTH bars only; the signal bar is evaluated after close and the staged engine enters no earlier than the next bar.

Parameter space before testing: `entry.params.min_extreme_break_ticks` in `[1, 2]`, `entry.params.max_delta_progress_ratio` in `[0.05, 0.1]`, `sl.params.stop_pct` in `[0.001, 0.0015, 0.0025]`, and fixed `tp.params.target_r_multiple=1.0` for 12 total combinations.

No NQ rescue attempt is authorized after results.

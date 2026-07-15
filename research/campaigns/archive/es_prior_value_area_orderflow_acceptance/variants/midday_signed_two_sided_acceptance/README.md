# midday_signed_two_sided_acceptance

Midday prior value-area signed-flow two-sided acceptance.

Mechanic: From 11:30 through 14:00 ET, enter long above prior VAH or short below prior VAL after a completed 5-minute close beyond the configured buffer, requiring same-direction total signed-volume imbalance on the completed signal bar.

Lookahead control: prior value-area levels are computed only after the previous RTH session is complete; the signal uses the completed 5-minute bar and the engine enters on the next bar open.

Parameter grid: `entry.params.breakout_buffer_ticks` x `entry.params.min_orderflow_imbalance` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 81 combinations.

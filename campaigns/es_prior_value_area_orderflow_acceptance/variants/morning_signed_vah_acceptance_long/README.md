# morning_signed_vah_acceptance_long

Morning prior-VAH signed-flow acceptance long.

Mechanic: From 09:35 through 11:30 ET, use prior-session approximate value-area levels only. Enter long after a completed 5-minute ES bar closes above prior VAH plus the configured buffer and the same completed bar has nonnegative-to-positive signed-volume imbalance above the configured threshold.

Lookahead control: prior value-area levels are computed only after the previous RTH session is complete; the signal uses the completed 5-minute bar and the engine enters on the next bar open.

Parameter grid: `entry.params.breakout_buffer_ticks` x `entry.params.min_orderflow_imbalance` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 81 combinations.

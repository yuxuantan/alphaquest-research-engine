# afternoon_large20_two_sided_acceptance

Afternoon prior value-area large-20 two-sided acceptance.

Mechanic: From 13:00 through 15:30 ET, enter long above prior VAH or short below prior VAL after a completed 5-minute close beyond the configured buffer, requiring same-direction large-20 signed-flow imbalance on the completed signal bar.

Lookahead control: prior value-area levels are computed only after the previous RTH session is complete; the signal uses the completed 5-minute bar and the engine enters on the next bar open.

Parameter grid: `entry.params.breakout_buffer_ticks` x `entry.params.min_orderflow_imbalance` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 81 combinations.

# late_morning_large10_two_sided_pivot_acceptance

Late-morning large10 two-sided value-area acceptance with completed pivot bias.

Mechanic: From 10:00 through 12:30 ET, enter long above prior VAH or short below prior VAL after completed 5-minute acceptance with same-direction large10 imbalance, filtered by carried completed 5/15-minute pivot direction.

Why it should be profitable: This should be profitable only if larger-trade aggregate participation confirms a real migration away from prior value after opening noise has settled and the last completed pivot structure supports continuation.

Lookahead control: prior value-area levels are computed only after the previous RTH session is complete; orderflow and pivot state use completed bars; entry is next-bar open or later.

Parameter grid: `entry.params.base_params.breakout_buffer_ticks` x `entry.params.base_params.min_orderflow_imbalance` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 54 combinations. Target R values are `[1.0, 1.5]`.

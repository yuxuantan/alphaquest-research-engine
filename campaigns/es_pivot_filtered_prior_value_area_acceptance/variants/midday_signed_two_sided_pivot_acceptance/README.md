# midday_signed_two_sided_pivot_acceptance

Midday signed-flow two-sided value-area acceptance with completed pivot bias.

Mechanic: From 11:30 through 14:00 ET, enter long above prior VAH or short below prior VAL after completed acceptance with total signed-flow confirmation, filtered by carried completed 5/15-minute pivot direction.

Why it should be profitable: This should be profitable only if midday value migration has enough remaining session time to continue and the completed pivot state prevents fading into opposing intraday structure.

Lookahead control: prior value-area levels are computed only after the previous RTH session is complete; orderflow and pivot state use completed bars; entry is next-bar open or later.

Parameter grid: `entry.params.base_params.breakout_buffer_ticks` x `entry.params.base_params.min_orderflow_imbalance` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 54 combinations. Target R values are `[1.0, 1.5]`.

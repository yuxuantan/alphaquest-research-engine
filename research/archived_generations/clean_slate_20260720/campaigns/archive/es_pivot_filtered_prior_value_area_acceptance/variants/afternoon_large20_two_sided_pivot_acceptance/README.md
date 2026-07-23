# afternoon_large20_two_sided_pivot_acceptance

Afternoon large20 two-sided value-area acceptance with completed pivot bias.

Mechanic: From 13:00 through 15:30 ET, enter long above prior VAH or short below prior VAL after completed acceptance with large20 flow confirmation, filtered by carried completed 5/15-minute pivot direction.

Why it should be profitable: This should be profitable only if late-session value migration is supported by larger trade-size participation and completed swing structure, while the 15:55 flatten still leaves enough room to realize at least 1R.

Lookahead control: prior value-area levels are computed only after the previous RTH session is complete; orderflow and pivot state use completed bars; entry is next-bar open or later.

Parameter grid: `entry.params.base_params.breakout_buffer_ticks` x `entry.params.base_params.min_orderflow_imbalance` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 54 combinations. Target R values are `[1.0, 1.5]`.

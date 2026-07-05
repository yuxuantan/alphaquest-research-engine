# morning_signed_vah_pivot_acceptance_long

From 09:35 through 11:30 ET, enter long only after a completed 5-minute NQ close accepts above prior VAH with signed-flow confirmation and completed 5/15-minute pivot structure supports long with no short opposition.

Why it should be profitable: This should be profitable only if NQ value migration away from the prior RTH value area persists when same-direction aggregate orderflow and completed swing-pivot structure agree.

Lookahead control: prior value-area levels are computed only after the previous RTH session is complete; orderflow and pivot state use completed bars only; entry is next-bar open or later; flatten is same-day.

Parameter grid: `entry.params.base_params.breakout_buffer_ticks` x `entry.params.base_params.min_orderflow_imbalance` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 54 combinations. Target R values are `[1.0, 1.5]`.

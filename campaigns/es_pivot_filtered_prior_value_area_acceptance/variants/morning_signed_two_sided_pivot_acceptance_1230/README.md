# morning_signed_two_sided_pivot_acceptance_1230

Morning signed-flow two-sided value-area acceptance with completed pivot bias.

Mechanic: From 09:35 through 12:30 ET, enter long above prior VAH or short below prior VAL after completed 5-minute acceptance with signed-flow confirmation, but only when carried completed 5/15-minute pivot structure agrees with the breakout direction and does not oppose it.

Why it should be profitable: This broader morning expression replaces the too-sparse short-only draft before PnL. It should be profitable only if early value migration persists when price acceptance, aggregate participation, and completed swing-pivot direction all agree.

Lookahead control: prior value-area levels are computed only after the previous RTH session is complete; orderflow and pivot state use completed bars; entry is next-bar open or later.

Parameter grid: `entry.params.base_params.breakout_buffer_ticks` x `entry.params.base_params.min_orderflow_imbalance` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 54 combinations. Target R values are `[1.0, 1.5]`.

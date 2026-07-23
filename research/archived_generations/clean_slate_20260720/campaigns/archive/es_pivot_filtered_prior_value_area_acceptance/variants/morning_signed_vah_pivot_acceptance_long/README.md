# morning_signed_vah_pivot_acceptance_long

Morning prior-VAH signed-flow acceptance long with completed pivot bias.

Mechanic: From 09:35 through 11:30 ET, enter long only after a completed 5-minute close accepts above prior VAH with signed-flow confirmation, and only when carried completed 5/15-minute pivot structure has at least one long state and no short state.

Why it should be profitable: This should be profitable only if acceptance above yesterday value continues when completed pivot structure already supports upside value migration, reducing random stop-probe breaks above VAH.

Lookahead control: prior value-area levels are computed only after the previous RTH session is complete; orderflow and pivot state use completed bars; entry is next-bar open or later.

Parameter grid: `entry.params.base_params.breakout_buffer_ticks` x `entry.params.base_params.min_orderflow_imbalance` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 54 combinations. Target R values are `[1.0, 1.5]`.

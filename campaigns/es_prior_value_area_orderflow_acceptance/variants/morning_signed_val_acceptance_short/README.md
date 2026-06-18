# morning_signed_val_acceptance_short

Morning prior-VAL signed-flow acceptance short.

Mechanic: From 09:35 through 11:30 ET, use prior-session approximate value-area levels only. Enter short after a completed 5-minute ES bar closes below prior VAL minus the configured buffer and the same completed bar has signed-volume imbalance at or below the negative configured threshold.

Lookahead control: prior value-area levels are computed only after the previous RTH session is complete; the signal uses the completed 5-minute bar and the engine enters on the next bar open.

Parameter grid: `entry.params.breakout_buffer_ticks` x `entry.params.min_orderflow_imbalance` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 81 combinations.

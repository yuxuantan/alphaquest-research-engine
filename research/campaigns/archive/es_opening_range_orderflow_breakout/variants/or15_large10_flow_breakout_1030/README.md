# or15_large10_flow_breakout_1030

Campaign: `es_opening_range_orderflow_breakout`

Mechanic: build the completed first 15-minute RTH opening range, then allow one two-sided breakout entry before 10:30 ET only when the completed 5-minute breakout bar closes beyond the range and large-10 aggregate flow is aligned.

Why this expresses the edge: the opening range supplies the price-action reference level; aggregate signed flow confirms that aggressive participation is pushing in the breakout direction instead of price merely touching a widely watched level.

Entry module: `opening_range_orderflow_breakout`.
Stop module: `opening_range_edge`.
Target module: `fixed_r`.

Parameter grid: `entry.params.breakout_buffer_ticks` x `entry.params.min_orderflow_imbalance` x `sl.params.max_stop_points` x `tp.params.target_r_multiple` = 81 combinations.

Lookahead controls: opening-range values are available only after their configured window completes, the signal uses a completed 5-minute bar, and the engine enters at the next bar open.

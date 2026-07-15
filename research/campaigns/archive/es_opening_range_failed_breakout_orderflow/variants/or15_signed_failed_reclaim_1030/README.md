# or15_signed_failed_reclaim_1030

Campaign: `es_opening_range_failed_breakout_orderflow`

Mechanic: build the completed first 15-minute RTH opening range, require a completed close outside the range, then trade the completed reclaim back through the same boundary before 10:30:00 only when the reclaim bar has opposite aggregate signed volume.

Why this expresses the edge: the opening range supplies the public support/resistance level, the failed outside close identifies trapped breakout participation, and the opposite-flow reclaim bar is the aggregate-orderflow confirmation.

Entry module: `opening_range_failed_breakout_orderflow`.
Stop module: `opening_range_edge`.
Target module: `opening_range_opposite_edge`.

Parameter grid: `entry.params.max_reclaim_bars` x `entry.params.min_reclaim_orderflow_imbalance` x `sl.params.stop_offset_ticks` = 12 combinations.

Lookahead controls: opening-range values are available only after the configured opening window, the failed breakout and reclaim both use completed closes, and the engine enters at the next bar open.

# midday_5_15_first_bias_1130_1400 rescue1

Parameter-space rescue only. Entry module, pivot sequence mechanic, time window, stop module, target module, data, costs, session, and validation gates are unchanged.

Changed before rescue testing: `entry.params.min_pivot_move_ticks` grid to `[4, 6, 8]`; fixed review value to `4`; `sl.params.stop_pct` grid to `[0.003, 0.005, 0.007]`; fixed review value to `0.005`. TP grid remains `[1.0, 1.5, 2.0]`; no target below 1.0R is allowed.

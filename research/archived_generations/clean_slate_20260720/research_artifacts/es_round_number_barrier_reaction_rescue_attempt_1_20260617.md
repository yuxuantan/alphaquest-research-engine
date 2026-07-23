# ES Round-Number Barrier Reaction Rescue Attempt 1

Decision: FAIL

All five failed original variants received exactly one rescue run. The rescue changed only predeclared numeric parameter space and fixed defaults:

- `entry.params.barrier_interval_points`: `[10.0, 25.0, 50.0]`
- `entry.params.buffer_ticks`: `[0, 1]`
- `sl.params.stop_pct`: `[0.001, 0.002, 0.0035]`
- `tp.params.target_r_multiple`: `[1.5, 2.5, 3.5]`

No entry module, stop module, target module, setup mode, direction, time window, data window, timeframe, costs, fill rules, session rules, prop rules, or validation gate was changed.

| variant | original profitable combos | original benchmark passes | rescue profitable combos | rescue benchmark passes | rescue terminal stage |
|---|---:|---:|---:|---:|---|
| morning_round_support_reclaim_long | 9 | 0 | 4 | 0 | limited_core_grid_test |
| morning_round_resistance_reject_short | 8 | 3 | 11 | 2 | limited_core_grid_test |
| midday_two_sided_round_reclaim | 0 | 0 | 0 | 0 | limited_core_grid_test |
| round_number_upside_breakout_long | 10 | 0 | 11 | 0 | limited_core_grid_test |
| round_number_downside_breakout_short | 10 | 8 | 11 | 4 | limited_core_grid_test |

Conclusion: rescue failed closed. No run reached monkey, WFA, Monte Carlo, incubation, or frozen validation.

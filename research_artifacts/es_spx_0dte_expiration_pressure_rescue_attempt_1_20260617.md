# ES SPX 0DTE Expiration Pressure Rescue Attempt 1 - 2026-06-17

All five failed original variants received exactly one parameter-space-only rescue. No entry module, stop module, target module, core edge, data window, timeframe, costs, fill assumptions, session rules, prop rules, or validation gates were changed.

| Variant | Original terminal | Rescue terminal | Key result |
|---|---|---|---|
| `full_week_down_move_fade_long_1000` | `limited_core_grid_test` | `limited_core_grid_test` | core_rate=0.6666666666666666; benchmark_pass=1; top_net=18540.0 |
| `full_week_up_move_fade_short_1000` | `limited_core_grid_test` | `limited_core_grid_test` | core_rate=0.2222222222222222; benchmark_pass=0; top_net=2310.0 |
| `tue_thu_two_sided_fade_1030` | `limited_core_grid_test` | `limited_core_grid_test` | core_rate=0.0; benchmark_pass=0; top_net=-2447.5 |
| `mwf_two_sided_fade_1030` | `limited_core_grid_test` | `limited_core_grid_test` | core_rate=0.4444444444444444; benchmark_pass=0; top_net=7722.5 |
| `full_week_late_move_continuation_1430` | `limited_core_grid_test` | `walk_forward_analysis` | core_rate=0.8518518518518519; WFA early_exit=True; stitched PF=0.5265575653172553; MAR=-1.5399289192985244; net=-4122.5 |

Decision: FAIL. The only rescue to reach WFA failed by early exit and negative stitched OOS metrics.

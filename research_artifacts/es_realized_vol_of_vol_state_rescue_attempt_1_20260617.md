# ES Realized Volatility-of-Volatility Rescue Attempt 1

Decision: FAIL

All five failed original variants received exactly one rescue run. The rescue changed only predeclared numeric parameter space and fixed defaults:

- `entry.params.vov_rank_threshold`: `[0.20, 0.30, 0.40]`
- `sl.params.stop_pct`: `[0.001, 0.002, 0.0035]`
- `tp.params.target_r_multiple`: `[1.5, 2.5, 3.5]`

No entry module, stop module, target module, feature construction, rank/value column, direction mode, entry time, data window, costs, fill rules, session rules, prop rules, or validation gate was changed.

| variant | original terminal stage | original profitable combos | rescue terminal stage | rescue profitable combos | rescue benchmark passes |
|---|---|---:|---|---:|---:|
| high_1d_vov_premium_long_1000 | limited_core_grid_test | 0 | limited_core_grid_test | 0 | 0 |
| high_1d_vov_stress_short_1030 | limited_core_grid_test | 0 | limited_core_grid_test | 0 | 0 |
| low_1d_vov_calm_long_1130 | limited_core_grid_test | 0 | limited_core_grid_test | 0 | 0 |
| high_5d_vov_premium_long_1200 | limited_core_grid_test | 0 | limited_core_grid_test | 5 | 0 |
| two_sided_20d_vov_state_1330 | limited_core_grid_test | 0 | limited_core_grid_test | 0 | 0 |

Conclusion: rescue failed closed. No run reached monkey, WFA, Monte Carlo, incubation, or frozen validation.

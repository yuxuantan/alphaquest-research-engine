# NQ Europe Equity Close Spillover Campaign Summary

Decision: FAIL

| Variant | Terminal Stage | Core Profitable Rate | Benchmark Pass Combos | Top Net | Top PF | Fixed Net | Fixed PF | Top Failure |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| dax_1d_strength_long_1330 | limited_core_grid_test | 0.333333 | 0/27 | 1155.00 | 1.110632 | 745.00 | 1.071946 | max_best_day_concentration |
| dax_1d_weakness_short_1330 | limited_core_grid_test | 0.000000 | 0/27 | -710.00 | 0.951034 | -1300.00 | 0.910003 | min_total_net_profit |
| europe_broad_weakness_short_1500 | limited_core_grid_test | 0.000000 | 0/27 | -1725.00 | 0.839684 | -2775.00 | 0.749096 | min_total_net_profit |
| stoxx_1d_strength_long_1400 | limited_core_grid_test | 0.111111 | 0/27 | 105.00 | 1.011188 | 95.00 | 1.010026 | max_best_day_concentration |
| stoxx_1d_weakness_short_1400 | limited_core_grid_test | 0.444444 | 9/27 | 4280.00 | 1.477679 | -725.00 | 0.936208 | none_on_top_cell_but_stage_failed_stability |

All five variants stopped at limited_core_grid_test. No variant reached limited monkey testing, WFA, WFA OOS monkey, WFA OOS Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

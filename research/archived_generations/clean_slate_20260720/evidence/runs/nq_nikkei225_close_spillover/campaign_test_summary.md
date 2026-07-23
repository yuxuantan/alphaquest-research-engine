# NQ Nikkei 225 Close Spillover Campaign Summary

Decision: FAIL

Run2 is the valid staged evidence. Run1 is preserved only as an infrastructure-error retry caused by unsupported `data.feature_set` usage.

| Variant | Terminal Stage | Core Profitable Rate | Benchmark Pass Combos | Top Net | Top PF | Monkey Net Beat | Monkey DD Beat |
|---|---:|---:|---:|---:|---:|---:|---:|
| nikkei_1d_strength_long_1000 | limited_core_grid_test | 0.000000 | 0/27 | -195.00 | 0.987004 | skipped | skipped |
| nikkei_1d_weakness_short_1000 | limited_core_grid_test | 0.481481 | 3/27 | 2732.50 | 1.129779 | skipped | skipped |
| nikkei_5d_strength_long_1030 | limited_monkey_test | 0.888889 | 15/27 | 2945.00 | 1.200136 | 0.81975 | 0.87175 |
| nikkei_5d_weakness_short_1030 | limited_monkey_test | 0.777778 | 16/27 | 4105.00 | 1.266299 | 0.946125 | 0.88675 |
| nikkei_1d_volatility_short_1130 | limited_core_grid_test | 0.222222 | 2/27 | 2355.00 | 1.139061 | skipped | skipped |

No variant reached WFA, WFA OOS monkey, WFA OOS Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

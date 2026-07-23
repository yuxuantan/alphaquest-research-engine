# NQ BTC Crypto Risk Sentiment Campaign Summary

Decision: FAIL

| Variant | Terminal Stage | Core Profitable Rate | Benchmark Pass Combos | Top Net | Top PF | Fixed Net | Fixed PF | Monkey Net Beat | Monkey DD Beat |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| btc_1d_strength_long_1000 | limited_core_grid_test | 0.000000 | 0/27 | -382.50 | 0.987890 | -6720.00 | 0.763505 |  |  |
| btc_1d_weakness_short_1000 | limited_core_grid_test | 0.037037 | 0/27 | 130.00 | 1.007656 | -7490.00 | 0.714667 |  |  |
| btc_3d_strength_long_1030 | limited_core_grid_test | 0.407407 | 5/27 | 4620.00 | 1.179070 | -1850.00 | 0.922594 |  |  |
| btc_3d_weakness_short_1130 | limited_core_grid_test | 0.111111 | 0/27 | 2075.00 | 1.107624 | -1455.00 | 0.931754 |  |  |
| btc_volatility_riskoff_short_1330 | limited_monkey_test | 0.925926 | 5/27 | 4440.00 | 1.316127 | 155.00 | 1.010010 | 0.73475 | 0.676875 |

Four variants stopped at limited_core_grid_test. `btc_volatility_riskoff_short_1330` reached limited_monkey_test but failed robustness. No variant reached WFA, WFA OOS monkey, WFA OOS Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

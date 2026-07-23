# NQ Industrial Production State Campaign Summary

Decision: FAIL

Four variants failed limited_core_grid_test; ipman_3m_weakness_long_1000 passed limited core but failed limited_monkey_test because max-drawdown beat rate was below 0.90. No branch reached WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

| Variant | Terminal Stage | Core Profitable Rate | Benchmark Pass | Top Net | Fixed Net | Monkey Net Beat | Monkey DD Beat |
|---|---|---:|---:|---:|---:|---:|---:|
| cumfns_3m_weakness_long_1330 | limited_core_grid_test | 0.0 | 0/27 | -370.0 | -3717.5 |  |  |
| indpro_3m_strength_long_1200 | limited_core_grid_test | 0.0 | 0/27 | -2990.0 | -3822.5 |  |  |
| ipman_3m_strength_short_1030 | limited_core_grid_test | 0.037037037037037035 | 0/27 | 430.0 | -2835.0 |  |  |
| ipman_3m_weakness_long_1000 | limited_monkey_test | 0.8888888888888888 | 14/27 | 2062.5 | 1117.5 | 0.9455 | 0.83275 |
| ipman_6m_weakness_long_1130 | limited_core_grid_test | 0.0 | 0/27 | -60.0 | -3535.0 |  |  |

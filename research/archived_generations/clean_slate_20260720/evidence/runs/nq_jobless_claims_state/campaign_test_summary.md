# NQ Jobless Claims State Campaign Summary

Decision: FAIL

All five variants failed limited_core_grid_test; claims_rising_short_1030 had only 1/27 profitable iterations, and no variant met the 0.70 profitable-iteration stability threshold. No branch reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

| Variant | Terminal Stage | Core Profitable Rate | Benchmark Pass | Top Net | Fixed Net | Monkey Net Beat | Monkey DD Beat |
|---|---|---:|---:|---:|---:|---:|---:|
| claims_improving_long_1130 | limited_core_grid_test | 0.0 | 0/27 | -825.0 | -3630.0 |  |  |
| claims_low_long_1000 | limited_core_grid_test | 0.0 | 0/27 | -570.0 | -1850.0 |  |  |
| claims_rising_short_1030 | limited_core_grid_test | 0.037037037037037035 | 0/27 | 200.0 | -1322.5 |  |  |
| continued_claims_improving_long_1330 | limited_core_grid_test | 0.0 | 0/27 | -750.0 | -1717.5 |  |  |
| continued_claims_rising_short_1200 | limited_core_grid_test | 0.0 | 0/27 | -1540.0 | -2110.0 |  |  |

# NQ ES Cross-Index Lead-Lag - Campaign Summary

Verdict: FAIL

One variant passed limited core but failed monkey robustness. The other four variants failed the limited core grid. No variant reached WFA, downstream Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

| Variant | Terminal stage | Core profitable | Top net | Top PF | Top trades | Top MAR | Monkey |
|---|---:|---:|---:|---:|---:|---:|---:|
| early30_two_sided_lag_follow_1000 | limited_monkey_test | 65/81 | 1942.5 | 1.1954225352112675 | 159 | 1.1660760743577445 | failed |
| early15_two_sided_lag_follow_1030 | limited_core_grid_test | 0/54 | -3185.0 | 0.6498075865860363 | 128 | -0.6321832638715877 | skipped |
| late_morning60_two_sided_lag_follow_1130 | limited_core_grid_test | 0/81 | -1415.0 | 0.831044776119403 | 122 | -0.5111499330542261 | skipped |
| midday60_confirmed_lag_follow_1230 | limited_core_grid_test | 0/36 | -1740.0 | 0.7993079584775087 | 98 | -0.319764174397272 | skipped |
| late_day30_confirmed_lag_follow_1530 | limited_core_grid_test | 0/36 | -1510.0 | 0.8064102564102564 | 120 | -0.5417389123502457 | skipped |

No rescue was authorized or used.

# NQ Treasury Rate Shock Intraday Campaign Summary

Decision: FAIL

All five variants failed limited_core_grid_test. Best profitable-rate was rate_up_high_level_short_1030 at 19/36 (0.5277777777777778), below the 0.70 gate. Across all official variants, 20/162 combinations were profitable, 0 benchmark-pass rows, and 0 Apex-rule-violating iterations. No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or acceptance OOS.

| Variant | Terminal stage | Profitable combos | Profitable rate | Top net | Top PF | Monkey net | Monkey DD | Apex violations |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `rate_up_short_1000` | limited_core_grid_test | 0/27 | 0.0000 | -2020.0 | 0.7681 |  |  | 0 |
| `rate_down_long_1000` | limited_core_grid_test | 1/27 | 0.0370 | 115.0 | 1.0118 |  |  | 0 |
| `rate_up_high_level_short_1030` | limited_core_grid_test | 19/36 | 0.5278 | 760.0 | 1.8539 |  |  | 0 |
| `bear_steepening_short_1130` | limited_core_grid_test | 0/36 | 0.0000 | -1665.0 | 0.7670 |  |  | 0 |
| `bull_flattening_long_1130` | limited_core_grid_test | 0/36 | 0.0000 | -60.0 | 0.9959 |  |  | 0 |

Results CSV: `backtest-campaigns/nq_treasury_rate_shock_intraday/campaign_results.csv`

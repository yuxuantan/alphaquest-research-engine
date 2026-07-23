# NQ Amihud Illiquidity Price Impact Campaign Summary

Decision: FAIL

All five variants failed limited_core_grid_test. Best profitable-rate was high_1d_illiq_stress_short_1030 at 11/27 (0.4074074074074074), below the 0.70 gate. Across all official variants, 21/135 combinations were profitable, 4 benchmark-pass rows, and 0 Apex-rule-violating iterations. No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or acceptance OOS.

| Variant | Terminal stage | Profitable combos | Profitable rate | Top net | Top PF | Monkey net | Monkey DD | Apex violations |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `high_1d_illiq_premium_long_1000` | limited_core_grid_test | 9/27 | 0.3333 | 1035.0 | 1.1121 |  |  | 0 |
| `high_1d_illiq_stress_short_1030` | limited_core_grid_test | 11/27 | 0.4074 | 795.0 | 1.0602 |  |  | 0 |
| `high_5d_illiq_premium_long_1130` | limited_core_grid_test | 1/27 | 0.0370 | 140.0 | 1.0109 |  |  | 0 |
| `high_20d_illiq_premium_long_1200` | limited_core_grid_test | 0/27 | 0.0000 | -610.0 | 0.9367 |  |  | 0 |
| `two_sided_5d_illiq_state_1330` | limited_core_grid_test | 0/27 | 0.0000 | -4915.0 | 0.5647 |  |  | 0 |

Results CSV: `backtest-campaigns/nq_amihud_illiquidity_price_impact/campaign_results.csv`

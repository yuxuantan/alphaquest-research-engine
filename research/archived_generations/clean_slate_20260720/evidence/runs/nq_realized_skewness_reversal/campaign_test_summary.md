# NQ Realized Skewness Reversal Campaign Summary

Decision: FAIL

All five variants failed limited_core_grid_test. Best profitable-rate was low_3d_skew_midmorning_long_1030 at 10/27 (0.37037037037037035), below the 0.70 gate. Across all official variants, 20/135 combinations were profitable, 3 benchmark-pass rows, and 0 Apex-rule-violating iterations. No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or acceptance OOS.

| Variant | Terminal stage | Profitable combos | Profitable rate | Top net | Top PF | Apex violations |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `low_1d_skew_open_long_1000` | limited_core_grid_test | 6/27 | 0.2222 | 2070.0 | 1.2232 | 0 |
| `high_1d_skew_open_short_1000` | limited_core_grid_test | 0/27 | 0.0000 | -492.5 | 0.9248 | 0 |
| `low_3d_skew_midmorning_long_1030` | limited_core_grid_test | 10/27 | 0.3704 | 1525.0 | 1.2059 | 0 |
| `high_3d_skew_midday_short_1200` | limited_core_grid_test | 3/27 | 0.1111 | 640.0 | 1.0658 | 0 |
| `two_sided_5d_skew_extreme_1330` | limited_core_grid_test | 1/27 | 0.0370 | 165.0 | 1.0065 | 0 |

Results CSV: `backtest-campaigns/nq_realized_skewness_reversal/campaign_results.csv`

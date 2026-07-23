# NQ Realized Volatility-of-Volatility State Campaign Summary

Decision: FAIL

All five variants failed limited_core_grid_test. Best profitable-rate was high_1d_vov_premium_long_1000 at 4/27 (0.14814814814814814), below the 0.70 gate. Across all official variants, 5/135 combinations were profitable, 3 benchmark-pass rows, and 0 Apex-rule-violating iterations. No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or acceptance OOS.

| Variant | Terminal stage | Profitable combos | Profitable rate | Top net | Top PF | Apex violations |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `high_1d_vov_premium_long_1000` | limited_core_grid_test | 4/27 | 0.1481 | 1180.0 | 1.0917 | 0 |
| `high_1d_vov_stress_short_1030` | limited_core_grid_test | 0/27 | 0.0000 | -305.0 | 0.9579 | 0 |
| `low_1d_vov_calm_long_1130` | limited_core_grid_test | 1/27 | 0.0370 | 330.0 | 1.0340 | 0 |
| `high_5d_vov_premium_long_1200` | limited_core_grid_test | 0/27 | 0.0000 | -220.0 | 0.9546 | 0 |
| `two_sided_20d_vov_state_1330` | limited_core_grid_test | 0/27 | 0.0000 | -2505.0 | 0.8991 | 0 |

Results CSV: `backtest-campaigns/nq_realized_vol_of_vol_state/campaign_results.csv`

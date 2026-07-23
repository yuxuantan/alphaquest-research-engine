# NQ Variance Risk Premium Intraday Campaign Summary

Decision: FAIL

All five variants failed limited_core_grid_test. Best profitable-rate was high_vrp_ratio_midday_long_1200 at 1/27 (0.037037037037037035), below the 0.70 gate. Across all official variants, 1/189 combinations were profitable, 0 benchmark-pass rows, and 0 Apex-rule-violating iterations. No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or acceptance OOS.

| Variant | Terminal stage | Profitable combos | Profitable rate | Top net | Top PF | Monkey net | Monkey DD | Apex violations |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `high_vrp_open_long_1000` | limited_core_grid_test | 0/27 | 0.0000 | -292.5 | 0.9476 |  |  | 0 |
| `low_vrp_open_short_1000` | limited_core_grid_test | 0/27 | 0.0000 | -635.0 | 0.8914 |  |  | 0 |
| `high_vrp_low_realized_midmorning_long_1030` | limited_core_grid_test | 0/81 | 0.0000 | -360.0 | 0.8484 |  |  | 0 |
| `high_vrp_ratio_midday_long_1200` | limited_core_grid_test | 1/27 | 0.0370 | 340.0 | 1.0354 |  |  | 0 |
| `vrp_rising_afternoon_long_1330` | limited_core_grid_test | 0/27 | 0.0000 | -15.0 | 0.9976 |  |  | 0 |

Results CSV: `backtest-campaigns/nq_variance_risk_premium_intraday/campaign_results.csv`

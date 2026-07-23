# NQ Dollar Risk-Appetite Intraday Campaign Summary

Decision: FAIL

All five variants failed limited_core_grid_test. Best profitable-rate was high_dollar_up_short_1130 at 7/54 (0.12962962962962962), below the 0.70 gate. Across all official variants, 8/162 combinations were profitable, 2 benchmark-pass rows, and 0 Apex-rule-violating iterations. No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or acceptance OOS.

| Variant | Terminal stage | Profitable combos | Profitable rate | Top net | Top PF | Monkey net | Monkey DD | Apex violations |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `dollar_up_risk_off_short_1000` | limited_core_grid_test | 0/27 | 0.0000 | -2330.0 | 0.6938 |  |  | 0 |
| `dollar_down_risk_on_long_1030` | limited_core_grid_test | 0/27 | 0.0000 | -955.0 | 0.9272 |  |  | 0 |
| `high_dollar_up_short_1130` | limited_core_grid_test | 7/54 | 0.1296 | 2020.0 | 1.1673 |  |  | 0 |
| `five_day_dollar_up_short_1200` | limited_core_grid_test | 1/27 | 0.0370 | 430.0 | 1.0294 |  |  | 0 |
| `five_day_dollar_down_long_1330` | limited_core_grid_test | 0/27 | 0.0000 | -1575.0 | 0.6572 |  |  | 0 |

Results CSV: `backtest-campaigns/nq_dollar_risk_appetite_intraday/campaign_results.csv`

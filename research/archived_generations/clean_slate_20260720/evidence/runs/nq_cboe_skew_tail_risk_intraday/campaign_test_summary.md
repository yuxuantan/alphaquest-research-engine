# NQ Cboe SKEW Tail Risk Intraday Campaign Summary

Decision: FAIL

All five variants failed limited_core_grid_test. Best profitable-rate was high_skew_short_1000 at 0/27 (0.0), below the 0.70 gate. Across all official variants, 0/135 combinations were profitable, 1 benchmark-pass rows, and 0 Apex-rule-violating iterations. No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or acceptance OOS.

| Variant | Terminal stage | Profitable combos | Profitable rate | Top net | Top PF | Monkey net | Monkey DD | Apex violations |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `high_skew_short_1000` | limited_core_grid_test | 0/27 | 0.0000 | 0.0 | 1.0000 |  |  | 0 |
| `low_skew_long_1030` | limited_core_grid_test | 0/27 | 0.0000 | -1490.0 | 0.9013 |  |  | 0 |
| `rising_skew_short_1130` | limited_core_grid_test | 0/27 | 0.0000 | -1930.0 | 0.7166 |  |  | 0 |
| `falling_skew_long_1200` | limited_core_grid_test | 0/27 | 0.0000 | -980.0 | 0.8863 |  |  | 0 |
| `persistent_high_skew_short_1330` | limited_core_grid_test | 0/27 | 0.0000 | -790.0 | 0.8198 |  |  | 0 |

Results CSV: `backtest-campaigns/nq_cboe_skew_tail_risk_intraday/campaign_results.csv`

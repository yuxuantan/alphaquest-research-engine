# NQ EMV Macro-News Intraday Campaign Summary

Decision: FAIL

All five variants failed limited_core_grid_test. Best profitable-rate was high_interest_news_short_1200 at 18/27 (0.6666666666666666), below the 0.70 gate. Across all official variants, 30/135 combinations were profitable, 3 benchmark-pass rows, and 0 Apex-rule-violating iterations. No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or acceptance OOS.

| Variant | Terminal stage | Profitable combos | Profitable rate | Top net | Top PF | Monkey net | Monkey DD | Apex violations |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `high_macro_news_short_1030` | limited_core_grid_test | 3/27 | 0.1111 | 1040.0 | 1.1345 |  |  | 0 |
| `high_macro_news_rebound_long_1130` | limited_core_grid_test | 9/27 | 0.3333 | 1125.0 | 1.0854 |  |  | 0 |
| `rising_macro_news_short_1000` | limited_core_grid_test | 0/27 | 0.0000 | -2440.0 | 0.7316 |  |  | 0 |
| `high_interest_news_short_1200` | limited_core_grid_test | 18/27 | 0.6667 | 885.0 | 1.1909 |  |  | 0 |
| `high_labor_news_short_1330` | limited_core_grid_test | 0/27 | 0.0000 | -1805.0 | 0.8741 |  |  | 0 |

Results CSV: `backtest-campaigns/nq_emv_macro_news_intraday/campaign_results.csv`

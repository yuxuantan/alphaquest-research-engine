# NQ Consumer Sentiment State Intraday Campaign Summary

Decision: FAIL

All five variants failed limited_core_grid_test. Best profitable-rate was falling_sentiment_short_1200 at 3/27 (0.1111111111111111), below the 0.70 gate. Across all official variants, 3/135 combinations were profitable, 1 benchmark-pass rows, and 0 Apex-rule-violating iterations. No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or acceptance OOS.

| Variant | Terminal stage | Profitable combos | Profitable rate | Top net | Top PF | Monkey net | Monkey DD | Apex violations |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `low_sentiment_long_1000` | limited_core_grid_test | 0/27 | 0.0000 | -685.0 | 0.9768 |  |  | 0 |
| `high_sentiment_short_1030` | limited_core_grid_test | 0/27 | 0.0000 | 0.0 | 0.0000 |  |  | 0 |
| `rising_sentiment_long_1130` | limited_core_grid_test | 0/27 | 0.0000 | -700.0 | 0.9243 |  |  | 0 |
| `falling_sentiment_short_1200` | limited_core_grid_test | 3/27 | 0.1111 | 1115.0 | 1.0968 |  |  | 0 |
| `low_sentiment_ma_long_1330` | limited_core_grid_test | 0/27 | 0.0000 | -4350.0 | 0.7280 |  |  | 0 |

Results CSV: `backtest-campaigns/nq_consumer_sentiment_state_intraday/campaign_results.csv`

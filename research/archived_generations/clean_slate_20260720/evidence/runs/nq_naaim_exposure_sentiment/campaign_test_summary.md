# NQ NAAIM Exposure Sentiment Campaign Summary

Decision: FAIL

All five variants failed limited_core_grid_test. Best profitable-rate was level_median_contrarian_1000 at 0/9 (0.0), below the 0.70 gate. Across all official variants, 0/45 combinations were profitable, 0 benchmark-pass rows, and 0 Apex-rule-violating iterations. No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or acceptance OOS.

| Variant | Terminal stage | Profitable combos | Profitable rate | Top net | Top PF | Monkey net | Monkey DD | Apex violations |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `level_median_contrarian_1000` | limited_core_grid_test | 0/9 | 0.0000 | -455.0 | 0.8606 |  |  | 0 |
| `level_rank_contrarian_1030` | limited_core_grid_test | 0/9 | 0.0000 | -400.0 | 0.9537 |  |  | 0 |
| `weekly_change_contrarian_1130` | limited_core_grid_test | 0/9 | 0.0000 | -1025.0 | 0.8064 |  |  | 0 |
| `zscore_sign_contrarian_1200` | limited_core_grid_test | 0/9 | 0.0000 | -560.0 | 0.9073 |  |  | 0 |
| `ma_distance_contrarian_1400` | limited_core_grid_test | 0/9 | 0.0000 | -1065.0 | 0.8035 |  |  | 0 |

Results CSV: `backtest-campaigns/nq_naaim_exposure_sentiment/campaign_results.csv`

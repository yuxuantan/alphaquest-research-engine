# NQ FOMC Pre-Announcement Drift Campaign Summary

Decision: FAIL

All five variants failed limited_core_grid_test. Best profitable-rate was decision_day_low_range_long_1130 at 0/27 (0.0), below the 0.70 gate. Across all official variants, 0/81 combinations were profitable, 0 benchmark-pass rows, and 0 Apex-rule-violating iterations. No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or acceptance OOS.

| Variant | Terminal stage | Profitable combos | Profitable rate | Top net | Top PF | Monkey net | Monkey DD | Apex violations |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `decision_day_open_long_1000` | limited_core_grid_test | 0/9 | 0.0000 | -212.5 | 0.8032 |  |  | 0 |
| `decision_day_late_morning_long_1130` | limited_core_grid_test | 0/9 | 0.0000 | -120.0 | 0.7176 |  |  | 0 |
| `decision_day_momentum_confirmed_long_1130` | limited_core_grid_test | 0/27 | 0.0000 | -145.0 | 0.5972 |  |  | 0 |
| `decision_day_low_range_long_1130` | limited_core_grid_test | 0/27 | 0.0000 | -105.0 | 0.5882 |  |  | 0 |
| `prior_day_late_long_1500` | limited_core_grid_test | 0/9 | 0.0000 | -395.0 | 0.4552 |  |  | 0 |

Results CSV: `backtest-campaigns/nq_fomc_pre_announcement_drift/campaign_results.csv`

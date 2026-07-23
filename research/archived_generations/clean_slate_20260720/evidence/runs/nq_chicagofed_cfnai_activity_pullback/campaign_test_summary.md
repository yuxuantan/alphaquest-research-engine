# NQ Chicago Fed CFNAI Activity Pullback Campaign Summary

Decision: FAIL

All five official NQ CFNAI activity-pullback variants failed limited_core_grid_test. No variant reached limited_monkey_test, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or acceptance OOS. Best profitable-iteration rate was production_income_weak_pullback_long_1100 at 0.4691, below the required 0.70. Apex rule violations were zero across all five limited-core grids.

| Variant | Profitable combos | Profitable rate | Benchmark-pass combos | Top net | Top PF | Top MAR | Apex violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `production_income_weak_pullback_long_1100` | 38/81 | 0.4691 | 18 | 3815.0 | 1.2671 | 1.4661 | 0 |
| `headline_activity_weak_pullback_long_1100` | 32/81 | 0.3951 | 7 | 1780.0 | 1.1389 | 0.4280 | 0 |
| `ma3_activity_weak_pullback_long_1130` | 0/81 | 0.0000 | 0 | -2090.0 | 0.8707 | -0.3610 | 0 |
| `diffusion_weak_pullback_long_1200` | 9/81 | 0.1111 | 0 | 1757.5 | 1.2759 | 0.7285 | 0 |
| `employment_hours_weak_pullback_long_1330` | 0/81 | 0.0000 | 0 | -2300.0 | 0.7695 | -0.4551 | 0 |

Results CSV: `backtest-campaigns/nq_chicagofed_cfnai_activity_pullback/campaign_results.csv`

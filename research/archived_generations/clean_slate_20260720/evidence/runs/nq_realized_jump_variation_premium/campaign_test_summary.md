# NQ Realized Jump Variation Premium Campaign Summary

Decision: FAIL

Four variants failed limited_core_grid_test. positive_jump_reversal_short_1200 passed limited core with 21/27 profitable combinations but failed limited_monkey_test on max-drawdown robustness: 0.866875 versus the 0.90 gate, while net-profit beat rate was 0.9515. No variant reached WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or acceptance OOS. Apex rule violations were zero in all completed stages.

| Variant | Terminal stage | Profitable combos | Profitable rate | Top net | Top PF | Monkey net | Monkey DD | Apex violations |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `high_jump_var_open_long_1000` | limited_core_grid_test | 0/27 | 0.0000 | -140.0 | 0.9852 |  |  | 0 |
| `high_3d_jump_var_midmorning_long_1030` | limited_core_grid_test | 0/27 | 0.0000 | -540.0 | 0.9215 |  |  | 0 |
| `negative_jump_rebound_long_1130` | limited_core_grid_test | 1/27 | 0.0370 | 115.0 | 1.0071 |  |  | 0 |
| `positive_jump_reversal_short_1200` | limited_monkey_test | 21/27 | 0.7778 | 4565.0 | 1.6144 | 0.9515 | 0.8669 | 0 |
| `two_sided_signed_jump_extreme_1330` | limited_core_grid_test | 0/81 | 0.0000 | -2525.0 | 0.7328 |  |  | 0 |

Results CSV: `backtest-campaigns/nq_realized_jump_variation_premium/campaign_results.csv`

# NQ FINRA Margin Leverage Campaign Summary

Decision: FAIL

Four variants failed limited_core_grid_test. rapid_margin_3m_expansion_short_1130 passed limited core with 22/27 profitable combinations (0.8148148148148148) but failed limited_monkey_test on max-drawdown robustness: 0.883375 versus the 0.90 gate, while net-profit beat rate was 0.92225. No variant reached WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or acceptance OOS. Apex rule violations were zero in all completed stages.

| Variant | Terminal stage | Profitable combos | Profitable rate | Top net | Top PF | Monkey net | Monkey DD | Apex violations |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `rapid_margin_1m_expansion_short_1030` | limited_core_grid_test | 9/27 | 0.3333 | 1247.5 | 1.1735 |  |  | 0 |
| `rapid_margin_3m_expansion_short_1130` | limited_monkey_test | 22/27 | 0.8148 | 2032.5 | 1.9176 | 0.9223 | 0.8834 | 0 |
| `persistent_margin_12m_expansion_short_1200` | limited_core_grid_test | 12/27 | 0.4444 | 400.0 | 2.0526 |  |  | 0 |
| `debit_credit_ratio_expansion_short_1330` | limited_core_grid_test | 0/27 | 0.0000 | -925.0 | 0.8356 |  |  | 0 |
| `margin_deleveraging_rebound_long_1430` | limited_core_grid_test | 0/27 | 0.0000 | -260.0 | 0.9303 |  |  | 0 |

Results CSV: `backtest-campaigns/nq_finra_margin_leverage/campaign_results.csv`

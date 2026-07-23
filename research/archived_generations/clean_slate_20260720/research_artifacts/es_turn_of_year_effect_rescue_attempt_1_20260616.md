# ES Turn-of-Year Effect Rescue Attempt 1

Date: 2026-06-16

Campaign: `es_turn_of_year_effect`

Decision: FAIL.

Scope: each failed variant received exactly one rescue. The rescue changed only declared fixed parameters or parameter space inside the existing `turn_of_year_effect`, `percent_from_entry`, and `fixed_r` modules. It did not change the turn-of-year date rule, direction, signal date source, timeframe, data window, costs, fill assumptions, stage gates, or edge thesis.

## Results

| Variant | Run | Terminal stage | Profitable combo rate | Benchmark pass combos | Top net | Top PF | Top trades | Decision |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `santa_window_open_long_1000` | `rescue1` | `limited_core_grid_test` | 0.16666666666666666 | 0 | 135.0 | 1.217741935483871 | 8 | FAIL |
| `santa_window_midday_long_1200` | `rescue1` | `limited_core_grid_test` | 0.0 | 0 | -215.0 | 0.5222222222222223 | 8 | FAIL |
| `december_window_long_1500` | `rescue1` | `limited_core_grid_test` | 0.3333333333333333 | 0 | 125.0 | 2.3513513513513513 | 5 | FAIL |
| `january_first2_open_long_1000` | `rescue1` | `limited_core_grid_test` | 0.4166666666666667 | 0 | 222.5 | 2.435483870967742 | 3 | FAIL |
| `santa_momentum_confirmed_midday_long_1200` | `rescue1` | `limited_core_grid_test` | 0.0 | 0 | -32.5 | 0.8243243243243243 | 4 | FAIL |

Best rescue: `january_first2_open_long_1000/rescue1`; it failed core with `0.4166666666666667` profitable combinations and zero benchmark-passing combinations. No run earned monkey, WFA, Monte Carlo, simulated incubation, or frozen validation.

Aggregate summary: `backtest-campaigns/es_turn_of_year_effect/campaign_test_summary.json`
Results table: `backtest-campaigns/es_turn_of_year_effect/campaign_results.csv`

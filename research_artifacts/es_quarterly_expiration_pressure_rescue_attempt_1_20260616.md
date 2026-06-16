# ES Quarterly Expiration Pressure Rescue Attempt 1

Date: 2026-06-16

Campaign: `es_quarterly_expiration_pressure`

Decision: FAIL.

Scope: each failed variant received exactly one rescue. The rescue changed only the declared stop/target parameter space inside the existing `quarterly_expiration_pressure`, `percent_from_entry`, and `fixed_r` modules. It did not change the expiration-date rule, direction, signal time, timeframe, data window, costs, fill assumptions, stage gates, or edge thesis.

## Results

| Variant | Run | Terminal stage | Profitable combo rate | Benchmark pass combos | Top net | Top PF | Top trades | Monkey profitable | Monkey median net | Decision |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `monday_prior_roll_week_long_1000` | `rescue1` | `limited_core_grid_test` | 0.0 | 0 | -328.125 | 0.08216783216783216 | 5 |  |  | FAIL |
| `thursday_prior_positioning_short_1330` | `rescue1` | `limited_core_grid_test` | 0.4166666666666667 | 0 | 404.375 | 3.0474683544303796 | 6 |  |  | FAIL |
| `expiration_friday_open_short_1000` | `rescue1` | `limited_core_grid_test` | 0.6666666666666666 | 0 | 1432.5 | 4.4939024390243905 | 6 |  |  | FAIL |
| `expiration_friday_midday_long_1200` | `rescue1` | `limited_core_grid_test` | 0.0 | 0 | -198.75 | 0.6434977578475336 | 6 |  |  | FAIL |
| `monday_after_expiration_reversal_long_1000` | `rescue1` | `limited_monkey_test` | 1.0 | 0 | 970.0 | 5.127659574468085 | 6 | 0.47 | -30.0 | FAIL |


Best rescue: `monday_after_expiration_reversal_long_1000/rescue1`. It passed the core profitable-combo gate with `1.0` profitable combinations but had only `6` top-combo trades, zero benchmark-passing combinations, and failed `limited_monkey_test` with `percentage_profitable=0.47` and `median_net_profit=-30.0`. The strategy therefore did not earn WFA, Monte Carlo, simulated incubation, or frozen validation.

Aggregate summary: `backtest-campaigns/es_quarterly_expiration_pressure/campaign_test_summary.json`
Results table: `backtest-campaigns/es_quarterly_expiration_pressure/campaign_results.csv`

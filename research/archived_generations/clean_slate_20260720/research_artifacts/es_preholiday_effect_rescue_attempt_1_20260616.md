# ES Pre-Holiday Effect Rescue Attempt 1

Date: 2026-06-16

Campaign: `es_preholiday_effect`

Decision: FAIL.

Scope: each failed variant received exactly one rescue. The rescue changed only declared fixed parameters or parameter space inside the existing `preholiday_effect`, `percent_from_entry`, and `fixed_r` modules. It did not change the holiday-date rule, direction, signal date source, timeframe, data window, costs, fill assumptions, stage gates, or edge thesis.

## Results

| Variant | Run | Terminal stage | Profitable combo rate | Benchmark pass combos | Top net | Top PF | Top trades | Decision |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `preholiday_open_long_1000` | `rescue1` | `limited_core_grid_test` | 0.0 | 0 | -127.5 | 0.9017341040462428 | 13 | FAIL |
| `preholiday_midday_long_1200` | `rescue1` | `limited_core_grid_test` | 0.16666666666666666 | 0 | 128.75 | 1.231981981981982 | 13 | FAIL |
| `preholiday_late_long_1500` | `rescue1` | `limited_core_grid_test` | 0.5 | 0 | 88.125 | 1.235 | 13 | FAIL |
| `preholiday_low_range_midday_long_1200` | `rescue1` | `limited_core_grid_test` | 0.027777777777777776 | 0 | 15.0 | 1.0205479452054795 | 12 | FAIL |
| `preholiday_momentum_confirmed_midday_long_1200` | `rescue1` | `limited_core_grid_test` | 0.5 | 0 | 232.5 | 2.2567567567567566 | 6 | FAIL |

Best rescue: `preholiday_momentum_confirmed_midday_long_1200/rescue1`; it failed core with `0.5` profitable combinations and zero benchmark-passing combinations. No run earned monkey, WFA, Monte Carlo, simulated incubation, or frozen validation.

Aggregate summary: `backtest-campaigns/es_preholiday_effect/campaign_test_summary.json`
Results table: `backtest-campaigns/es_preholiday_effect/campaign_results.csv`

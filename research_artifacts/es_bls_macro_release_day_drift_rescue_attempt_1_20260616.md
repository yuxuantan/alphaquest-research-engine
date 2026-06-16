# ES BLS Macro Release-Day Drift Rescue Attempt 1

Date: 2026-06-16

Campaign: `es_bls_macro_release_day_drift`

Decision: FAIL.

Scope: each failed variant received exactly one rescue. The rescue changed only
declared fixed parameters or parameter space inside the existing
`bls_macro_release_day_drift`, `percent_from_entry`, and `fixed_r` modules. It
did not change release-date membership, release-type set, direction, entry time,
timeframe, data window, costs, fill assumptions, stage gates, or edge thesis.

## Results

| Variant | Run | Terminal stage | Profitable combo rate | Benchmark pass combos | Top net | Top PF | Top trades | Decision |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `employment_release_open_long_1000` | `rescue1` | `limited_core_grid_test` | 0.5833333333333334 | 0 | 465.0 | 1.382716049382716 | 17 | FAIL |
| `cpi_release_open_long_1000` | `rescue1` | `limited_core_grid_test` | 0.08333333333333333 | 0 | 353.125 | 1.216973886328725 | 20 | FAIL |
| `combined_bls_release_open_long_1000` | `rescue1` | `limited_core_grid_test` | 0.0 | 0 | -60.0 | 0.9774859287054409 | 37 | FAIL |
| `combined_bls_release_momentum_long_1130` | `rescue1` | `limited_core_grid_test` | 0.0 | 0 | -26.875 | 0.9263698630136986 | 6 | FAIL |
| `combined_bls_release_low_range_long_1200` | `rescue1` | `limited_core_grid_test` | 0.07407407407407407 | 0 | 65.625 | 1.2524038461538463 | 5 | FAIL |

Best rescue: `employment_release_open_long_1000/rescue1`; it failed core with
`0.5833333333333334` profitable combinations, zero benchmark-passing
combinations, only `17` top-row trades, and top-row failure reason
`preferred_min_total_trades;max_best_day_concentration`. No run earned monkey,
WFA, Monte Carlo, simulated incubation, or frozen validation.

Aggregate summary:
`backtest-campaigns/es_bls_macro_release_day_drift/campaign_test_summary.json`

Results table:
`backtest-campaigns/es_bls_macro_release_day_drift/campaign_results.csv`

# ES Monthly OPEX Pressure Rescue Attempt 1

Date: 2026-06-16

Campaign: `es_monthly_opex_pressure`

Scope: each failed variant received exactly one rescue. The rescue changed only the declared stop/target parameter space inside the existing `monthly_opex_pressure`, `percent_from_entry`, and `fixed_r` modules. It did not change the monthly OPEX calendar, quarterly-month exclusion, signal type, direction, entry time, timeframe, data window, costs, fill assumptions, stage gates, or edge thesis.

Rescue parameter space:

- `sl.params.stop_pct`: `[0.001, 0.002, 0.003, 0.005]`
- `tp.params.target_r_multiple`: `[0.75, 1.25, 1.75]`
- Total combinations per rescue: `12`

| Variant | Run | Terminal stage | Profitable combo rate | Benchmark pass combos | Top net | Top PF | Top trades | Decision |
|---|---:|---|---:|---:|---:|---:|---:|---|
| `nonquarterly_opex_thursday_positioning_short_1330` | `rescue1` | `limited_core_grid_test` | 0.5833333333333334 | 0 | 830.625 | 2.1536458333333335 | 12 | FAIL |
| `nonquarterly_opex_open_short_1000` | `rescue1` | `limited_core_grid_test` | 0.16666666666666666 | 0 | 130.625 | 1.2464622641509433 | 12 | FAIL |
| `nonquarterly_opex_midday_long_1200` | `rescue1` | `limited_core_grid_test` | 0.25 | 0 | 165.0 | 1.318840579710145 | 12 | FAIL |
| `nonquarterly_opex_late_short_1500` | `rescue1` | `limited_core_grid_test` | 0.0 | 0 | -94.375 | 0.8971389645776566 | 12 | FAIL |
| `nonquarterly_post_opex_monday_reversal_long_1000` | `rescue1` | `limited_core_grid_test` | 0.16666666666666666 | 0 | 323.125 | 1.2201873935264054 | 11 | FAIL |

Best rescue: `nonquarterly_opex_thursday_positioning_short_1330/rescue1`; it still failed core with `0.5833333333333334` profitable combinations, zero benchmark-passing combinations, and only `12` top-combo trades. No run earned monkey, WFA, Monte Carlo, simulated incubation, or frozen validation.

Aggregate summary: `backtest-campaigns/es_monthly_opex_pressure/campaign_test_summary.json`

Results table: `backtest-campaigns/es_monthly_opex_pressure/campaign_results.csv`

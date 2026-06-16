# ES VIX Expiration Pressure Rescue Attempt 1

Date: 2026-06-16

Campaign: `es_vix_expiration_pressure`

Scope: each failed variant received exactly one rescue. The rescue changed only the declared stop/target parameter space inside the existing `vix_expiration_pressure`, `percent_from_entry`, and `fixed_r` modules. It did not change the VIX expiration calendar, signal type, direction, entry time, timeframe, data window, costs, fill assumptions, stage gates, or edge thesis.

Rescue parameter space:

- `sl.params.stop_pct`: `[0.001, 0.002, 0.003, 0.005]`
- `tp.params.target_r_multiple`: `[0.75, 1.25, 1.75]`
- Total combinations per rescue: `12`

| Variant | Run | Terminal stage | Profitable combo rate | Benchmark pass combos | Top net | Top PF | Top trades | Decision |
|---|---:|---|---:|---:|---:|---:|---:|---|
| `prior_session_late_hedge_unwind_long_1500` | `rescue1` | `limited_core_grid_test` | 0.0 | 0 | -326.875 | 0.4951737451737452 | 16 | FAIL |
| `vix_settlement_open_pressure_short_1000` | `rescue1` | `limited_core_grid_test` | 0.5833333333333334 | 0 | 2208.75 | 2.2004076086956523 | 17 | FAIL |
| `vix_settlement_midday_reversal_long_1200` | `rescue1` | `limited_core_grid_test` | 0.0 | 0 | -769.375 | 0.5420386904761905 | 17 | FAIL |
| `vix_settlement_late_reversal_long_1500` | `rescue1` | `limited_core_grid_test` | 0.0 | 0 | -575.625 | 0.5960526315789474 | 17 | FAIL |
| `post_vix_settlement_next_session_long_1000` | `rescue1` | `limited_core_grid_test` | 0.08333333333333333 | 0 | 96.25 | 1.044 | 17 | FAIL |

Best rescue: `vix_settlement_open_pressure_short_1000/rescue1`; it failed core with `0.5833333333333334` profitable combinations, zero benchmark-passing combinations, and only `17` top-combo trades. No run earned monkey, WFA, Monte Carlo, simulated incubation, or frozen validation.

Aggregate summary: `backtest-campaigns/es_vix_expiration_pressure/campaign_test_summary.json`

Results table: `backtest-campaigns/es_vix_expiration_pressure/campaign_results.csv`

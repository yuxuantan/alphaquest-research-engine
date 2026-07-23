# ES Rolling Range Orderflow Sweep Reversal Rescue Attempt 1

Date: 2026-06-17

Campaign: `es_rolling_range_orderflow_sweep_reversal`

Trigger: all five original variants failed `limited_core_grid_test`.

Allowed scope: one rescue per failed variant, changing only fixed parameters or declared parameter space inside existing entry, stop, and target modules.

Unchanged: entry module `rolling_range_orderflow_sweep_reversal`, stop module `sweep_extreme`, target module `fixed_r`, data, timeframe, costs, fills, sessions, prop rules, validation gates, and the rolling-range sweep-reclaim plus absorption mechanic.

Changes: require `min_sweep_ticks: 2`, longer rolling lookbacks, stronger absorption thresholds, and wider stop/target neighborhoods.

Result: FAIL.

All five original variants and all five one-time parameter-space/fixed-parameter rescues failed limited_core_grid_test before monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

| Variant | Top net | Top PF | Trades/year | Failure |
|---|---:|---:|---:|---|
| `afternoon_signed_24bar_sweep_reclaim_1500` | 675.00 | 1.4272 | 22.27 | min_trades_per_year;preferred_min_total_trades |
| `all_day_large20_36bar_sweep_reclaim_1500` | 65.00 | 1.3881 | 5.49 | min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |
| `midday_signed_24bar_sweep_reclaim_1400` | 395.00 | 1.1540 | 28.97 | min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |
| `morning_large10_12bar_sweep_reclaim_1130` | 0.00 | 0.0000 | 0.00 | min_trades_per_year;preferred_min_total_trades |
| `morning_signed_12bar_sweep_reclaim_1130` | 0.00 | 0.0000 | 0.00 | min_trades_per_year;preferred_min_total_trades |

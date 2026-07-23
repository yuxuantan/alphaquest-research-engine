# ES Round-Number Orderflow Barrier Campaign Summary

Decision: **FAIL**

All five original variants and all five one-time parameter-space rescues failed limited_core_grid_test before monkey, WFA, Monte Carlo, simulated incubation, or frozen validation.

| Variant | Run | Terminal stage | Profitable combo rate | Top net | Top PF | Top trades/year | Top failure |
|---|---|---|---:|---:|---:|---:|---|
| `midday_two_sided_large10_absorption_reclaim` | `run1` | `limited_core_grid_test` | 0.0185 | 105.00 | 1.0069 | 81.00 | max_best_day_concentration |
| `midday_two_sided_large10_absorption_reclaim` | `rescue1` | `limited_core_grid_test` | 0.0370 | 925.00 | 1.0619 | 81.66 | max_best_day_concentration |
| `morning_resistance_buy_absorption_short` | `run1` | `limited_core_grid_test` | 0.0741 | 650.00 | 1.0954 | 43.97 | min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |
| `morning_resistance_buy_absorption_short` | `rescue1` | `limited_core_grid_test` | 0.2037 | 2460.00 | 1.4013 | 45.99 | min_trades_per_year;preferred_min_total_trades |
| `morning_support_sell_absorption_long` | `run1` | `limited_core_grid_test` | 0.1111 | 1462.50 | 1.1508 | 46.31 | min_trades_per_year;preferred_min_total_trades |
| `morning_support_sell_absorption_long` | `rescue1` | `limited_core_grid_test` | 0.3519 | 2075.00 | 1.2182 | 49.61 | min_trades_per_year;preferred_min_total_trades |
| `round_number_downside_flow_breakout_short` | `run1` | `limited_core_grid_test` | 0.1296 | 2817.50 | 1.1636 | 84.13 |  |
| `round_number_downside_flow_breakout_short` | `rescue1` | `limited_core_grid_test` | 0.0741 | 3100.00 | 1.1789 | 84.78 |  |
| `round_number_upside_flow_breakout_long` | `run1` | `limited_core_grid_test` | 0.1481 | 1277.50 | 1.1425 | 47.04 | min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |
| `round_number_upside_flow_breakout_long` | `rescue1` | `limited_core_grid_test` | 0.0370 | 602.50 | 1.0896 | 47.04 | min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |

No run reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

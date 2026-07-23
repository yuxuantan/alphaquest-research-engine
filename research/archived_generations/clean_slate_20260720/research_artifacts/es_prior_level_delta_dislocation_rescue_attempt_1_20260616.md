# ES Prior-Level Delta Dislocation Rescue Attempt 1

Date: 2026-06-16

Decision: FAIL.

Scope: one rescue for each failed variant. The rescue changed only fixed parameters and declared parameter space inside the same `positive_delta_dislocation`, `percent_from_entry`, and `fixed_r` modules. It did not change the edge thesis, timeframe, data window, costs, fill assumptions, or validation gates.

Original fixed fresh-level flags produced zero trades because a first prior-level breach had to coincide with the completed 60-minute signal boundary. Rescue1 disabled the fixed fresh-level requirement and widened threshold grids, then retested the same prior-level price/orderflow dislocation mechanic.

| Variant | Run | Terminal stage | Profitable-combo rate | Top net | Top trades | Failure |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `pdh_buy_absorption_long` | `run1` | `limited_core_grid_test` | 0.0 | 0.0 | 0 | min_profit_factor;min_expectancy_r;min_mar;min_win_rate;min_trades_per_year;preferred_min_total_trades;min_positive_month_rate |
| `pdh_buy_absorption_long` | `rescue1` | `limited_core_grid_test` | 0.06172839506172839 | 102.5 | 12 | min_profit_factor;min_mar;min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |
| `pdh_buy_exhaustion_short` | `run1` | `limited_core_grid_test` | 0.0 | 0.0 | 0 | min_profit_factor;min_expectancy_r;min_mar;min_win_rate;min_trades_per_year;preferred_min_total_trades;min_positive_month_rate |
| `pdh_buy_exhaustion_short` | `rescue1` | `limited_core_grid_test` | 0.0 | -107.5 | 9 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;min_trades_per_year;preferred_min_total_trades |
| `pdl_sell_absorption_long` | `run1` | `limited_core_grid_test` | 0.0 | 0.0 | 0 | min_profit_factor;min_expectancy_r;min_mar;min_win_rate;min_trades_per_year;preferred_min_total_trades;min_positive_month_rate |
| `pdl_sell_absorption_long` | `rescue1` | `limited_core_grid_test` | 0.5555555555555556 | 437.5 | 15 | min_trades_per_year;preferred_min_total_trades |
| `pdl_sell_pressure_short` | `run1` | `limited_core_grid_test` | 0.0 | 0.0 | 0 | min_profit_factor;min_expectancy_r;min_mar;min_win_rate;min_trades_per_year;preferred_min_total_trades;min_positive_month_rate |
| `pdl_sell_pressure_short` | `rescue1` | `limited_core_grid_test` | 0.0 | -717.5 | 16 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;min_win_rate;min_trades_per_year;preferred_min_total_trades;min_positive_month_rate |
| `two_sided_auto_level_fade` | `run1` | `limited_core_grid_test` | 0.0 | 0.0 | 0 | min_profit_factor;min_expectancy_r;min_mar;min_win_rate;min_trades_per_year;preferred_min_total_trades;min_positive_month_rate |
| `two_sided_auto_level_fade` | `rescue1` | `limited_core_grid_test` | 0.0 | -114.375 | 16 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;min_trades_per_year;preferred_min_total_trades |

No run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.

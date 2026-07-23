# ES Market Plumbing Liquidity Capacity Campaign Summary

Decision: FAIL

All five corrected market-plumbing liquidity-capacity originals failed before WFA, and all five one-time parameter-space-only rescues also failed. Dealer-lending 13:30 original and dual-priority rescue reached limited monkey, but both failed the profitability/median robustness gate. No run reached WFA, Monte Carlo, simulated incubation, or acceptance validation.

## Results

| Variant | Run | Terminal stage | Profitable/monkey rate | Median net | Top net | Top PF | Top trades | Failure |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `dealer_lending_pressure_long_1130` | `run2` | `limited_core_grid_test` | 0.25925925925925924 |  | 2097.5 | 1.140277545560943 | 88 | min_profit_factor;preferred_min_total_trades;max_best_day_concentration |
| `dealer_lending_pressure_long_1130` | `rescue1` | `limited_core_grid_test` | 0.2222222222222222 |  | 1675.625 | 1.1214441021924262 | 88 | min_profit_factor;min_mar;preferred_min_total_trades |
| `dealer_lending_pressure_long_1330` | `run2` | `limited_monkey_test` | 0.25333333333333335 | -1962.5 | 3253.75 | 1.288133717068851 | 88 | min_profit_factor;preferred_min_total_trades |
| `dealer_lending_pressure_long_1330` | `rescue1` | `limited_core_grid_test` | 0.6666666666666666 |  | 3006.875 | 1.2639346061005048 | 88 | min_profit_factor;min_expectancy_r;preferred_min_total_trades |
| `vx_oi_stress_long_1330` | `run2` | `limited_core_grid_test` | 0.5555555555555556 |  | 3342.5 | 1.2833227378681924 | 94 | min_profit_factor;preferred_min_total_trades |
| `vx_oi_stress_long_1330` | `rescue1` | `limited_core_grid_test` | 0.6666666666666666 |  | 3167.5 | 1.2682049110922946 | 94 | min_profit_factor;min_expectancy_r;preferred_min_total_trades |
| `vx_oi_crowding_short_1330` | `run2` | `limited_core_grid_test` | 0.0 |  | -632.5 | 0.8855203619909502 | 39 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;min_trades_per_year;preferred_min_total_trades |
| `vx_oi_crowding_short_1330` | `rescue1` | `limited_core_grid_test` | 0.0 |  | -904.375 | 0.8444086021505376 | 39 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;min_trades_per_year;preferred_min_total_trades |
| `dual_pressure_priority_long_1130` | `run2` | `limited_core_grid_test` | 0.6790123456790124 |  | 8175.0 | 1.3493589743589745 | 145 | max_consecutive_losses;preferred_min_total_trades |
| `dual_pressure_priority_long_1130` | `rescue1` | `limited_monkey_test` | 0.3466666666666667 | -1665.0 | 8212.5 | 1.3683974430862398 | 145 | max_consecutive_losses;preferred_min_total_trades |

## Validation Note

`run1` artifacts are invalid data-loader checks caused by an unsupported descriptive `data.feature_set` label. Valid economic evidence starts with `run2`.

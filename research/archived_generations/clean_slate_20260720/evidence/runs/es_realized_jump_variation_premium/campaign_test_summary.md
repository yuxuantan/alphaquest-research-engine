# ES Realized Jump Variation Premium

Decision: FAIL.

All five original realized jump-variation variants failed limited_core_grid_test. Each failed variant received exactly one parameter-space/fixed-parameter rescue, preserving the same jump-feature construction, setup mode, direction, entry time, entry module, stop module, take-profit module, timeframe, data window, costs, and stage criteria. All five rescues also failed limited_core_grid_test; no run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation.

| Variant | Run | Terminal stage | Profitable combo rate | Top net | Top PF | Top trades | Failure |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `high_jump_share_midmorning_long_1030` | `run1` | `limited_core_grid_test` | 0.0 | -1562.5 | 0.893344709897611 | 110 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;min_positive_month_rate |
| `high_jump_var_open_long_1000` | `run1` | `limited_core_grid_test` | 0.0 | -2732.5 | 0.573546625048771 | 74 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;min_win_rate;max_consecutive_losses;preferred_min_total_trades;min_positive_month_rate |
| `negative_jump_rebound_long_1130` | `run1` | `limited_core_grid_test` | 0.0 | -1395.0 | 0.8785636561479869 | 89 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;min_positive_month_rate |
| `positive_jump_reversal_short_1200` | `run1` | `limited_core_grid_test` | 0.0 | -110.0 | 0.98661800486618 | 87 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar |
| `two_sided_signed_jump_extreme_1330` | `run1` | `limited_core_grid_test` | 0.0 | -3055.0 | 0.7450448570832464 | 121 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;min_win_rate;min_positive_month_rate |
| `high_jump_share_midmorning_long_1030` | `rescue1` | `limited_core_grid_test` | 0.0 | -573.75 | 0.9502923976608187 | 96 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;min_positive_month_rate |
| `high_jump_var_open_long_1000` | `rescue1` | `limited_core_grid_test` | 0.0 | -1236.25 | 0.414792899408284 | 51 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;min_trades_per_year;preferred_min_total_trades;min_positive_month_rate |
| `negative_jump_rebound_long_1130` | `rescue1` | `limited_core_grid_test` | 0.0 | -1165.0 | 0.7076537013801757 | 63 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;preferred_min_total_trades;min_positive_month_rate |
| `positive_jump_reversal_short_1200` | `rescue1` | `limited_core_grid_test` | 0.1111111111111111 | 2304.375 | 1.3012254901960785 | 66 | preferred_min_total_trades |
| `two_sided_signed_jump_extreme_1330` | `rescue1` | `limited_core_grid_test` | 0.0 | -4508.125 | 0.36505281690140845 | 151 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;max_consecutive_losses;min_positive_month_rate |

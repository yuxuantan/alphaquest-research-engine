# ES Treasury Rate Shock Intraday

Decision: FAIL.

All five original Treasury-rate shock variants failed limited_core_grid_test. Each failed variant received exactly one parameter-space-only rescue, preserving the same Treasury-rate feature construction, setup mode, direction, entry time, entry module, stop module, take-profit module, timeframe, data window, costs, and stage criteria. All five rescues also failed limited_core_grid_test; no run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation.

| Variant | Run | Terminal stage | Profitable combo rate | Top net | Top PF | Top MAR | Top trades | Failure |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `rate_up_short_1000` | `run1` | `limited_core_grid_test` | 0.0 | -5200.0 | 0.7445658848090384 | -0.5128496573263388 | 165 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;min_win_rate;max_consecutive_losses;min_positive_month_rate |
| `rate_down_long_1000` | `run1` | `limited_core_grid_test` | 0.0 | -4516.25 | 0.7396974063400577 | -0.5886221745042453 | 107 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;min_win_rate;max_consecutive_losses;min_positive_month_rate |
| `rate_up_high_level_short_1030` | `run1` | `limited_core_grid_test` | 0.027777777777777776 | 30.0 | 1.0389610389610389 | 0.0392158260340673 | 9 | min_profit_factor;min_mar;min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |
| `bear_steepening_short_1130` | `run1` | `limited_core_grid_test` | 0.0 | -8880.0 | 0.6099703524761173 | -0.7524016645838831 | 151 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;min_win_rate;min_positive_month_rate |
| `bull_flattening_long_1130` | `run1` | `limited_core_grid_test` | 0.0 | -2177.5 | 0.835318585743997 | -0.4045958783412387 | 103 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;max_consecutive_losses;min_positive_month_rate |
| `rate_up_short_1000` | `rescue1` | `limited_core_grid_test` | 0.0 | -5225.0 | 0.7080189997205923 | -0.5435421099735824 | 165 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;max_consecutive_losses;min_positive_month_rate |
| `rate_down_long_1000` | `rescue1` | `limited_core_grid_test` | 0.0 | -5092.5 | 0.5571739130434783 | -0.7205306045592635 | 171 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;max_consecutive_losses;min_positive_month_rate |
| `rate_up_high_level_short_1030` | `rescue1` | `limited_core_grid_test` | 0.08333333333333333 | 114.375 | 1.198051948051948 | 0.1993267837005205 | 9 | min_profit_factor;min_mar;min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |
| `bear_steepening_short_1130` | `rescue1` | `limited_core_grid_test` | 0.0 | -5929.375 | 0.5057824546780579 | -0.7283828198049106 | 124 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;max_consecutive_losses;min_positive_month_rate |
| `bull_flattening_long_1130` | `rescue1` | `limited_core_grid_test` | 0.0 | -2132.5 | 0.8180072541071047 | -0.5013842840830932 | 134 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;min_positive_month_rate |

# ES OFR Financial Stress Intraday

Decision: FAIL.

All five original OFR financial-stress variants failed limited_core_grid_test. Each failed variant received exactly one parameter-space-only rescue, preserving the same OFR feature construction, setup mode, direction, entry time, entry module, stop module, take-profit module, timeframe, data window, costs, OFR two-business-day availability lag, and stage criteria. All five rescues also failed limited_core_grid_test: the best rescue profitable-combo rates reached 0.5185185185185185 for credit and volatility variants, still below the required 0.70. No run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation.

| Variant | Run | Terminal stage | Profitable combo rate | Top net | Top PF | Top MAR | Top trades | Failure |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `rising_global_stress_short_1000` | `run1` | `limited_core_grid_test` | 0.0 | -757.5 | 0.9468700683850605 | -0.25481995834497456 | 124 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;min_win_rate |
| `rising_global_stress_short_1000` | `rescue1` | `limited_core_grid_test` | 0.07407407407407407 | 436.25 | 1.0285784474287587 | 0.19893214559094832 | 104 | min_profit_factor;min_mar;max_best_day_concentration |
| `high_credit_stress_short_1030` | `run1` | `limited_core_grid_test` | 0.0 | -202.5 | 0.993091684434968 | -0.04430321644792289 | 198 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;min_win_rate |
| `high_credit_stress_short_1030` | `rescue1` | `limited_core_grid_test` | 0.5185185185185185 | 4816.25 | 1.1366408965174835 | 1.1298599938968712 | 193 | min_profit_factor |
| `funding_stress_short_1130` | `run1` | `limited_core_grid_test` | 0.0 | -4510.0 | 0.8001993576254292 | -1.3653036911793301 | 142 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;min_win_rate;min_positive_month_rate |
| `funding_stress_short_1130` | `rescue1` | `limited_core_grid_test` | 0.3333333333333333 | 1932.5 | 1.075814044723421 | 0.7737327239451628 | 126 | min_profit_factor;max_best_day_concentration;min_positive_month_rate |
| `us_stress_short_1200` | `run1` | `limited_core_grid_test` | 0.0 | -1365.0 | 0.93271719038817 | -0.6149503762235313 | 138 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;min_win_rate;min_positive_month_rate |
| `us_stress_short_1200` | `rescue1` | `limited_core_grid_test` | 0.48148148148148145 | 2597.5 | 1.1007759456838022 | 0.9841509506131116 | 138 | min_profit_factor;max_best_day_concentration |
| `volatility_stress_short_1330` | `run1` | `limited_core_grid_test` | 0.0 | -1235.0 | 0.9202325205877604 | -0.5344378861780749 | 117 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;max_consecutive_losses;min_positive_month_rate |
| `volatility_stress_short_1330` | `rescue1` | `limited_core_grid_test` | 0.5185185185185185 | 2507.5 | 1.1784062611170403 | 1.6805890147552547 | 91 | min_profit_factor;min_positive_month_rate |

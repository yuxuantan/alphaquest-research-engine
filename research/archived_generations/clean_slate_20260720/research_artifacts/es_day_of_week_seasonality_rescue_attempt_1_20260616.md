# ES Day-of-Week Seasonality Rescue Attempt 1

Decision: FAIL.

Scope: one rescue per failed variant. Changed only stop/target parameter space; retained weekday maps, signal times, timeframe, data window, costs, fills, and validation gates.

| Variant | Run | Stage | Profitable Combos | Top Net | Top PF | Top Trades | Failure |
|---|---:|---|---:|---:|---:|---:|---|
| `friday_late_preweekend_long_1300` | `run1` | `limited_core_grid_test` | 0.0 | -2327.5 | 0.6489441930618401 | 73 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;preferred_min_total_trades;min_positive_month_rate |
| `friday_late_preweekend_long_1300` | `rescue1` | `limited_core_grid_test` | 0.0 | -2102.5 | 0.6726352666407163 | 73 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;preferred_min_total_trades;min_positive_month_rate |
| `friday_open_preweekend_long_0935` | `run1` | `limited_core_grid_test` | 0.0 | -2695.0 | 0.6922637739080788 | 74 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;min_win_rate;preferred_min_total_trades;min_positive_month_rate |
| `friday_open_preweekend_long_0935` | `rescue1` | `limited_core_grid_test` | 0.0 | -1314.375 | 0.5172176308539945 | 46 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;min_trades_per_year;preferred_min_total_trades;min_positive_month_rate |
| `mon_fri_polarity_pair_1000` | `run1` | `limited_core_grid_test` | 0.0 | -2612.5 | 0.784713638236506 | 130 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;preferred_min_total_trades;min_positive_month_rate |
| `mon_fri_polarity_pair_1000` | `rescue1` | `limited_core_grid_test` | 0.0 | -2900.0 | 0.5259501430322844 | 105 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;preferred_min_total_trades;min_positive_month_rate |
| `monday_late_weekend_short_1100` | `run1` | `limited_core_grid_test` | 0.0 | -3055.0 | 0.7026040399123874 | 66 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;min_win_rate;max_consecutive_losses;preferred_min_total_trades;min_positive_month_rate |
| `monday_late_weekend_short_1100` | `rescue1` | `limited_core_grid_test` | 0.0 | -1640.0 | 0.5460207612456748 | 63 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;preferred_min_total_trades;min_positive_month_rate |
| `monday_open_weekend_short_0935` | `run1` | `limited_core_grid_test` | 0.0 | -800.0 | 0.9208508533267376 | 65 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;preferred_min_total_trades;min_positive_month_rate |
| `monday_open_weekend_short_0935` | `rescue1` | `limited_core_grid_test` | 0.0 | -1328.125 | 0.8829330101366241 | 65 | min_total_net_profit;min_profit_factor;min_expectancy_r;min_cagr;min_mar;preferred_min_total_trades;min_positive_month_rate |

All originals and rescues failed before WFA. No candidate strategy report was created.

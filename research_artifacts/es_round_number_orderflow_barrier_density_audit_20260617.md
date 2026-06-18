# ES Round-Number Orderflow Barrier Density Audit

Pre-performance density check only. Counts use the proposed completed-bar entry
rules over prepared 5-minute RTH bars and do not inspect PnL.

Prepared data period: 2011-01-03 09:30:00 to 2026-06-09 15:55:00 America/New_York;
strategy rows=297726; session days=3817; approximate years=15.147.

| variant | barrier_interval_points | buffer_ticks | min_orderflow_imbalance | signal_days | approx_trades_per_year |
|---|---:|---:|---:|---:|---:|
| morning_support_sell_absorption_long | 25.0 | 0 | 0.01 | 1289 | 85.1 |
| morning_support_sell_absorption_long | 25.0 | 0 | 0.03 | 1051 | 69.4 |
| morning_support_sell_absorption_long | 25.0 | 0 | 0.05 | 805 | 53.1 |
| morning_support_sell_absorption_long | 25.0 | 1 | 0.01 | 1289 | 85.1 |
| morning_support_sell_absorption_long | 25.0 | 1 | 0.03 | 1060 | 70.0 |
| morning_support_sell_absorption_long | 25.0 | 1 | 0.05 | 823 | 54.3 |
| morning_resistance_buy_absorption_short | 25.0 | 0 | 0.01 | 1290 | 85.2 |
| morning_resistance_buy_absorption_short | 25.0 | 0 | 0.03 | 1083 | 71.5 |
| morning_resistance_buy_absorption_short | 25.0 | 0 | 0.05 | 804 | 53.1 |
| morning_resistance_buy_absorption_short | 25.0 | 1 | 0.01 | 1282 | 84.6 |
| morning_resistance_buy_absorption_short | 25.0 | 1 | 0.03 | 1063 | 70.2 |
| morning_resistance_buy_absorption_short | 25.0 | 1 | 0.05 | 797 | 52.6 |
| midday_two_sided_large10_absorption_reclaim | 25.0 | 0 | 0.03 | 2117 | 139.8 |
| midday_two_sided_large10_absorption_reclaim | 25.0 | 0 | 0.06 | 2050 | 135.3 |
| midday_two_sided_large10_absorption_reclaim | 25.0 | 0 | 0.09 | 1965 | 129.7 |
| midday_two_sided_large10_absorption_reclaim | 25.0 | 1 | 0.03 | 2219 | 146.5 |
| midday_two_sided_large10_absorption_reclaim | 25.0 | 1 | 0.06 | 2147 | 141.7 |
| midday_two_sided_large10_absorption_reclaim | 25.0 | 1 | 0.09 | 2066 | 136.4 |
| round_number_upside_flow_breakout_long | 25.0 | 1 | 0.01 | 2169 | 143.2 |
| round_number_upside_flow_breakout_long | 25.0 | 1 | 0.03 | 2062 | 136.1 |
| round_number_upside_flow_breakout_long | 25.0 | 1 | 0.05 | 1905 | 125.8 |
| round_number_upside_flow_breakout_long | 50.0 | 1 | 0.01 | 1254 | 82.8 |
| round_number_upside_flow_breakout_long | 50.0 | 1 | 0.03 | 1165 | 76.9 |
| round_number_upside_flow_breakout_long | 50.0 | 1 | 0.05 | 1034 | 68.3 |
| round_number_downside_flow_breakout_short | 25.0 | 1 | 0.01 | 2103 | 138.8 |
| round_number_downside_flow_breakout_short | 25.0 | 1 | 0.03 | 1991 | 131.4 |
| round_number_downside_flow_breakout_short | 25.0 | 1 | 0.05 | 1817 | 120.0 |
| round_number_downside_flow_breakout_short | 50.0 | 1 | 0.01 | 1206 | 79.6 |
| round_number_downside_flow_breakout_short | 50.0 | 1 | 0.03 | 1115 | 73.6 |
| round_number_downside_flow_breakout_short | 50.0 | 1 | 0.05 | 994 | 65.6 |

Conclusion: every declared entry corner is above the 50 trades/year pre-PnL
density floor. The sparse 50-point absorption corner was rejected before any PnL
testing and is not in the frozen campaign.

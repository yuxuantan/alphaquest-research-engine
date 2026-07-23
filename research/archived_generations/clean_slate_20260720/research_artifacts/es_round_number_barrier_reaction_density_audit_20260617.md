# ES Round-Number Barrier Reaction Density Audit

Pre-performance density check only. Counts use the frozen entry module over prepared 5-minute RTH bars and do not inspect PnL.

Prepared data period: 2011-01-03 09:30:00-05:00 to 2026-06-09 15:59:00-04:00; strategy rows=297726

| run_set | variant | barrier_interval_points | buffer_ticks | signal_days | approx_trades_per_year |
|---|---|---:|---:|---:|---:|
| original | midday_two_sided_round_reclaim | 25.0 | 0 | 2205 | 143.0 |
| original | midday_two_sided_round_reclaim | 25.0 | 1 | 2258 | 146.4 |
| original | midday_two_sided_round_reclaim | 50.0 | 0 | 1292 | 83.8 |
| original | midday_two_sided_round_reclaim | 50.0 | 1 | 1308 | 84.8 |
| original | morning_round_resistance_reject_short | 25.0 | 0 | 2076 | 134.6 |
| original | morning_round_resistance_reject_short | 25.0 | 1 | 2079 | 134.8 |
| original | morning_round_resistance_reject_short | 50.0 | 0 | 1151 | 74.6 |
| original | morning_round_resistance_reject_short | 50.0 | 1 | 1150 | 74.6 |
| original | morning_round_support_reclaim_long | 25.0 | 0 | 2085 | 135.2 |
| original | morning_round_support_reclaim_long | 25.0 | 1 | 2070 | 134.2 |
| original | morning_round_support_reclaim_long | 50.0 | 0 | 1162 | 75.4 |
| original | morning_round_support_reclaim_long | 50.0 | 1 | 1141 | 74.0 |
| original | round_number_downside_breakout_short | 25.0 | 0 | 1960 | 127.1 |
| original | round_number_downside_breakout_short | 25.0 | 1 | 1771 | 114.9 |
| original | round_number_downside_breakout_short | 50.0 | 0 | 1050 | 68.1 |
| original | round_number_downside_breakout_short | 50.0 | 1 | 946 | 61.3 |
| original | round_number_upside_breakout_long | 25.0 | 0 | 2055 | 133.3 |
| original | round_number_upside_breakout_long | 25.0 | 1 | 1854 | 120.2 |
| original | round_number_upside_breakout_long | 50.0 | 0 | 1125 | 73.0 |
| original | round_number_upside_breakout_long | 50.0 | 1 | 1017 | 66.0 |
| rescue | midday_two_sided_round_reclaim | 10.0 | 0 | 3342 | 216.7 |
| rescue | midday_two_sided_round_reclaim | 10.0 | 1 | 3419 | 221.7 |
| rescue | midday_two_sided_round_reclaim | 25.0 | 0 | 2205 | 143.0 |
| rescue | midday_two_sided_round_reclaim | 25.0 | 1 | 2258 | 146.4 |
| rescue | midday_two_sided_round_reclaim | 50.0 | 0 | 1292 | 83.8 |
| rescue | midday_two_sided_round_reclaim | 50.0 | 1 | 1308 | 84.8 |
| rescue | morning_round_resistance_reject_short | 10.0 | 0 | 3283 | 212.9 |
| rescue | morning_round_resistance_reject_short | 10.0 | 1 | 3282 | 212.8 |
| rescue | morning_round_resistance_reject_short | 25.0 | 0 | 2076 | 134.6 |
| rescue | morning_round_resistance_reject_short | 25.0 | 1 | 2079 | 134.8 |
| rescue | morning_round_resistance_reject_short | 50.0 | 0 | 1151 | 74.6 |
| rescue | morning_round_resistance_reject_short | 50.0 | 1 | 1150 | 74.6 |
| rescue | morning_round_support_reclaim_long | 10.0 | 0 | 3354 | 217.5 |
| rescue | morning_round_support_reclaim_long | 10.0 | 1 | 3360 | 217.9 |
| rescue | morning_round_support_reclaim_long | 25.0 | 0 | 2085 | 135.2 |
| rescue | morning_round_support_reclaim_long | 25.0 | 1 | 2070 | 134.2 |
| rescue | morning_round_support_reclaim_long | 50.0 | 0 | 1162 | 75.4 |
| rescue | morning_round_support_reclaim_long | 50.0 | 1 | 1141 | 74.0 |
| rescue | round_number_downside_breakout_short | 10.0 | 0 | 3195 | 207.2 |
| rescue | round_number_downside_breakout_short | 10.0 | 1 | 2939 | 190.6 |
| rescue | round_number_downside_breakout_short | 25.0 | 0 | 1960 | 127.1 |
| rescue | round_number_downside_breakout_short | 25.0 | 1 | 1771 | 114.9 |
| rescue | round_number_downside_breakout_short | 50.0 | 0 | 1050 | 68.1 |
| rescue | round_number_downside_breakout_short | 50.0 | 1 | 946 | 61.3 |
| rescue | round_number_upside_breakout_long | 10.0 | 0 | 3313 | 214.9 |
| rescue | round_number_upside_breakout_long | 10.0 | 1 | 3078 | 199.6 |
| rescue | round_number_upside_breakout_long | 25.0 | 0 | 2055 | 133.3 |
| rescue | round_number_upside_breakout_long | 25.0 | 1 | 1854 | 120.2 |
| rescue | round_number_upside_breakout_long | 50.0 | 0 | 1125 | 73.0 |
| rescue | round_number_upside_breakout_long | 50.0 | 1 | 1017 | 66.0 |

Conclusion: minimum pre-test density is 61.3 signals/year across the final declared original and rescue entry grids.
Rows below 50/year: 0

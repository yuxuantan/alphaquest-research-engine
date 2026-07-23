# NQ Morning Trend Lunch Reversal Orderflow Campaign Test Summary

Verdict: FAIL.

All five predeclared NQ morning trend lunch reversal orderflow variants failed limited_core_grid_test. Across 135 official core combinations, 0 were profitable, 0 passed benchmark gates, and 0 had Apex rule violations. The least-negative top row was late_morning_signed_down_extension_long_1130 with top net -440.00, PF 0.9339, and 155 trades, so no variant reached monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

The campaign passed pre-PnL density: 45/45 declared entry rows cleared the full-history, limited-core, and latest-window gates. PnL was inspected only through the staged limited-core grid.

| Variant | Top net | PF | Trades | Top params | Failure |
|---|---:|---:|---:|---|---|
| late_morning_signed_up_extension_short_1130 | -1045.00 | 0.8651 | 199 | morning=8.0, imb=0.04, stop=2.0, target=1.0 | min_total_net_profit;max_consecutive_losses |
| late_morning_signed_down_extension_long_1130 | -440.00 | 0.9339 | 155 | morning=16.0, imb=0.0, stop=2.0, target=1.0 | min_total_net_profit |
| lunch_signed_two_sided_reversal_1230 | -7300.00 | 0.4983 | 332 | morning=16.0, imb=0.04, stop=1.0, target=1.0 | min_total_net_profit;max_consecutive_losses |
| lunch_large10_two_sided_reversal_1300 | -7325.00 | 0.4945 | 346 | morning=16.0, imb=0.02, stop=1.0, target=1.0 | min_total_net_profit |
| early_afternoon_large20_two_sided_reversal_1400 | -2980.00 | 0.7693 | 329 | morning=12.0, imb=0.04, stop=4.0, target=1.0 | min_total_net_profit |

No monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate report was run because every variant failed the first staged gate.

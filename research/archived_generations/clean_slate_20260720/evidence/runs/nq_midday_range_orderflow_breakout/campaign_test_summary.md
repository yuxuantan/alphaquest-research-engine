# NQ Midday Range Orderflow Breakout Campaign Test Summary

Verdict: FAIL.

All five predeclared NQ midday range orderflow breakout variants failed limited_core_grid_test. Across 270 official core combinations, 0 were profitable, 0 passed benchmark gates, and 0 had Apex rule violations. The least-negative top row was lunch_1130_1300_signed_breakout_1430 with top net -370.00, PF 0.9754, and 261 trades, so no variant reached monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

The campaign passed pre-PnL density: 45/45 declared entry rows cleared the full-history, limited-core, and latest-window gates. PnL was inspected only through the staged limited-core grid.

| Variant | Flow | Top net | PF | Trades | Top params | Failure |
|---|---|---:|---:|---:|---|---|
| lunch_1130_1300_signed_breakout_1430 | signed_volume | -370.00 | 0.9754 | 261 | range=80, imb=0.0, stop=16, target=1.0 | min_total_net_profit;max_consecutive_losses |
| lunch_1130_1300_large10_breakout_1430 | large10 | -1665.00 | 0.9042 | 242 | range=80, imb=0.1, stop=16, target=1.5 | min_total_net_profit;max_consecutive_losses |
| lunch_1130_1300_large20_breakout_1430 | large20 | -3670.00 | 0.7848 | 236 | range=80, imb=0.05, stop=16, target=1.0 | min_total_net_profit |
| late_lunch_1200_1330_signed_breakout_1500 | signed_volume | -1110.00 | 0.9328 | 287 | range=80, imb=0.03, stop=16, target=1.0 | min_total_net_profit;max_consecutive_losses |
| late_lunch_1200_1330_large10_breakout_1500 | large10 | -2295.00 | 0.8669 | 278 | range=80, imb=0.0, stop=16, target=1.0 | min_total_net_profit |

No monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate report was run because every variant failed the first staged gate.

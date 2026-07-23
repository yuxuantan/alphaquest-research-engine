# NQ RTH Intraday Risk Premium Campaign Test Summary

Verdict: FAIL.

All five predeclared NQ RTH intraday risk-premium variants failed limited_core_grid_test. Across 5 fixed core combinations, 0 were profitable, 0 passed benchmark gates, and 0 had Apex rule violations. The least-negative fixed row was late_morning_1100_long with top net -510.00, PF 0.9884, and 371 trades, so no variant reached monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

The campaign passed pre-PnL density: 5/5 fixed entry rows produced daily signal availability across full history, limited core, and the latest 252 sessions. PnL was inspected only through the staged limited-core grid.

| Variant | Signal time | Net | PF | Trades | Failure |
|---|---:|---:|---:|---:|---|
| open_0935_long | 09:35:00 | -6865.00 | 0.8717 | 371 | min_total_net_profit;max_consecutive_losses |
| first_hour_1000_long | 10:00:00 | -7300.00 | 0.8527 | 371 | min_total_net_profit;max_consecutive_losses |
| midmorning_1030_long | 10:30:00 | -3075.00 | 0.9342 | 371 | min_total_net_profit |
| late_morning_1100_long | 11:00:00 | -510.00 | 0.9884 | 371 | min_total_net_profit;max_consecutive_losses |
| early_afternoon_1300_long | 13:00:00 | -6835.00 | 0.8126 | 371 | min_total_net_profit;max_consecutive_losses |

No monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate report was run because every variant failed the first staged gate.

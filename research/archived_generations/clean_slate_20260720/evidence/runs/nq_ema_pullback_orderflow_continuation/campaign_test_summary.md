# NQ EMA Pullback Orderflow Continuation Campaign Summary

Decision: FAIL.

Four NQ EMA pullback variants failed limited_core_grid_test. The short-only late-morning variant passed limited core and limited monkey but failed walk_forward_analysis by early exit before stitched OOS trading, so no branch reached WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

Pre-PnL density passed all 45 declared entry rows, so staged PnL was run. No rescue or parameter narrowing was used.

| Variant | Terminal stage | Profitable combo rate | Passing combos | Top net | Top PF | Top trades/year | Failure metric |
|---|---|---:|---:|---:|---:|---:|---|
| afternoon_large10_two_sided_ema_pullback_1430 | limited_core_grid_test | 0.00 | 0/27 | -4640.00 | 0.696 | 229.65 | summary.percentage_profitable_iterations |
| late_morning_signed_long_ema_pullback_1200 | limited_core_grid_test | 0.04 | 0/27 | 480.00 | 1.056 | 135.18 | summary.percentage_profitable_iterations |
| late_morning_signed_short_ema_pullback_1200 | walk_forward_analysis | 0.70 | 5/27 | 1045.00 | 1.115 | 125.90 | summary.early_exit|stitched_oos_metrics.profit_factor|stitched_oos_metrics.mar|stitched_oos_metrics.trades_per_year |
| late_morning_signed_two_sided_ema_pullback_1130 | limited_core_grid_test | 0.19 | 0/27 | 575.00 | 1.044 | 190.43 | summary.percentage_profitable_iterations |
| lunch_signed_two_sided_ema_pullback_1300 | limited_core_grid_test | 0.00 | 0/27 | -1175.00 | 0.925 | 234.86 | summary.percentage_profitable_iterations |

Best top-net variant: `late_morning_signed_short_ema_pullback_1200` with top net `1045.0` and PF `1.1154058531198232`. It still failed the full staged workflow.

No WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate report was produced.

# NQ Rolling Statistical Envelope Orderflow Reversion Campaign Summary

Decision: FAIL.

All five NQ rolling statistical-envelope orderflow-reversion variants failed limited_core_grid_test with 0 profitable combinations and 0 benchmark-passing combinations per variant. No branch reached monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

Pre-PnL density passed all 45 declared entry rows, so staged PnL was run. All staged branches stopped at limited_core_grid_test.

| Variant | Profitable combo rate | Passing combos | Top net | Top PF | Top trades/year | Failure metric |
|---|---:|---:|---:|---:|---:|---|
| morning_5m_signed_6bar_reversion_1130 | 0.00 | 0/54 | -5655.00 | 0.540 | 240.71 | summary.percentage_profitable_iterations |
| late_morning_5m_large10_12bar_reversion_1230 | 0.00 | 0/54 | -6465.00 | 0.470 | 240.69 | summary.percentage_profitable_iterations |
| midday_5m_signed_18bar_reversion_1400 | 0.00 | 0/54 | -5970.00 | 0.364 | 240.70 | summary.percentage_profitable_iterations |
| afternoon_5m_large20_24bar_reversion_1500 | 0.00 | 0/54 | -6295.00 | 0.337 | 238.72 | summary.percentage_profitable_iterations |
| all_day_1m_signed_30bar_reversion_1530 | 0.00 | 0/54 | -4125.00 | 0.544 | 240.71 | summary.percentage_profitable_iterations |

Best top-net variant: `all_day_1m_signed_30bar_reversion_1530` with top net `-4125.0` and PF `0.5439469320066335`. It still failed because profitable-combo rate was `0.0`, below the `0.7` gate.

No WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate report was produced.

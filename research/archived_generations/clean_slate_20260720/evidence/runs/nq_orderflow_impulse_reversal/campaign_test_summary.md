# NQ Orderflow-Impulse Reversal Campaign Summary

Decision: FAIL.

All five NQ orderflow-impulse reversal variants failed limited_core_grid_test with 0/27 profitable combinations and 0 benchmark-passing combinations per variant. No branch reached monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

Pre-PnL density passed all 45 declared entry rows, so staged PnL was run. All staged branches stopped at limited_core_grid_test.

| Variant | Profitable combo rate | Passing combos | Top net | Top PF | Top trades/year | Failure metric |
|---|---:|---:|---:|---:|---:|---|
| early_5m_impulse_reversal_1000 | 0.00 | 0/27 | -1075.00 | 0.544 | 54.86 | summary.percentage_profitable_iterations |
| late_morning_15m_impulse_reversal_1130 | 0.00 | 0/27 | -1220.00 | 0.466 | 56.70 | summary.percentage_profitable_iterations |
| midday_30m_impulse_reversal_1230 | 0.00 | 0/27 | -1500.00 | 0.259 | 62.41 | summary.percentage_profitable_iterations |
| afternoon_60m_impulse_reversal_1400 | 0.00 | 0/27 | -1050.00 | 0.641 | 83.99 | summary.percentage_profitable_iterations |
| late_day_30m_impulse_reversal_1500 | 0.00 | 0/27 | -875.00 | 0.609 | 66.00 | summary.percentage_profitable_iterations |

Best top-net variant: `late_day_30m_impulse_reversal_1500` with top net `-875.0` and PF `0.6085011185682326`. It still failed because profitable-combo rate was `0.0`, below the `0.7` gate.

No WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate report was produced.

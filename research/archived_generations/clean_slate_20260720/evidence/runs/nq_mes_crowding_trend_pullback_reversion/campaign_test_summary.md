# NQ MES-Crowding Trend-Pullback Reversion - Campaign Summary

Verdict: FAIL

The NQ base MES-crowding trend-pullback port did not produce a candidate strategy. Midday and early-afternoon variants passed the limited core grid but failed monkey robustness. Morning trade/notional and afternoon notional failed core.

| Variant | Terminal stage | Core profitable | Top net | Top PF | Top trades | Top MAR | Monkey | Monkey median net | Net beat rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| afternoon_notional_trend_pullback_reversal_1400 | limited_core_grid_test | 0/81 | -3070.0 | 0.7293962097840458 | 44 | -1.0342933123785258 | skipped | None | None |
| early_afternoon_notional_trend_pullback_reversal_1300 | limited_monkey_test | 81/81 | 6530.0 | 1.3137160701417248 | 49 | 1.2259110468547003 | failed | -730.0 | 0.661375 |
| midday_notional_trend_pullback_reversal_1200 | limited_monkey_test | 79/81 | 10420.0 | 1.4245263801181502 | 53 | 2.9780847065647635 | failed | -542.5 | 0.787 |
| morning_notional_trend_pullback_reversal_1030 | limited_core_grid_test | 42/81 | 10525.0 | 1.3692334678126645 | 67 | 1.755177871806761 | skipped | None | None |
| morning_trade_trend_pullback_reversal_1030 | limited_core_grid_test | 42/81 | 10585.0 | 1.3537176274018379 | 68 | 1.5620570382151615 | skipped | None | None |

No rescue was authorized or used.

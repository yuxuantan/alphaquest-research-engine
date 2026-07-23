# ES/MES Participation Crowding Reversion - Rescue Attempt 1

Decision: FAIL.

Scope: one parameter-space-only rescue for each failed original variant. The rescues kept the same entry module, stop module, target module, MES participation feature definitions, data window, costs, slippage, session rules, next-bar execution, pessimistic same-bar stop/target handling, and forced-flatten rules.

Original results:

| variant | terminal stage | profitable combo rate | top net | top PF | top trades/year |
|---|---:|---:|---:|---:|---:|
| `morning_notional_down_reversal_long_1030` | limited_core_grid_test | 0.4074074074074074 | 8450.0 | 1.5241122654675143 | 93.85256272994492 |
| `morning_notional_up_reversal_short_1030` | limited_core_grid_test | 0.2222222222222222 | 2570.0 | 1.3688554000717617 | 55.95104206989684 |
| `midday_notional_two_sided_reversal_1200` | limited_core_grid_test | 0.6419753086419753 | 7110.0 | 1.3322429906542057 | 127.70788195741501 |
| `afternoon_trade_down_reversal_long_1400` | limited_core_grid_test | 0.0 | -150.0 | 0.9918743228602384 | 79.37711800458243 |
| `afternoon_trade_up_reversal_short_1400` | limited_core_grid_test | 0.0 | -2612.5 | 0.7544642857142857 | 61.89876546115733 |

Rescue results:

| variant | terminal stage | profitable combo rate | monkey net beat | monkey drawdown beat | decision |
|---|---:|---:|---:|---:|---|
| `morning_notional_down_reversal_long_1030` | limited_monkey_test | 0.8395061728395061 | 0.8566666666666667 | 0.6833333333333333 | FAIL |
| `morning_notional_up_reversal_short_1030` | limited_core_grid_test | 0.5555555555555556 | n/a | n/a | FAIL |
| `midday_notional_two_sided_reversal_1200` | limited_monkey_test | 0.8024691358024691 | 0.79 | 0.8666666666666667 | FAIL |
| `afternoon_trade_down_reversal_long_1400` | limited_core_grid_test | 0.06172839506172839 | n/a | n/a | FAIL |
| `afternoon_trade_up_reversal_short_1400` | limited_core_grid_test | 0.0 | n/a | n/a | FAIL |

Conclusion: no run reached WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

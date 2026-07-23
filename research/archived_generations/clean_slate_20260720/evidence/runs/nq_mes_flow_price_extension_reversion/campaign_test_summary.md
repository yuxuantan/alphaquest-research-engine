# NQ MES Flow Price Extension Reversion

Verdict: FAIL

All five variants failed the staged flow. Four failed limited_core_grid_test stability and one passed core but failed limited_monkey_test robustness before WFA.

| variant | terminal stage | core profitable | benchmark pass | top net | top PF | monkey net beat | monkey DD beat |
|---|---:|---:|---:|---:|---:|---:|---:|
| `late_morning30_mes_buy_nq_up_extension_short_1030` | limited_core_grid_test | 36/81 | 0 | 5650.0 | 1.2411438326931286 | None | None |
| `late_morning30_mes_sell_nq_down_extension_long_1100` | limited_core_grid_test | 12/81 | 0 | 2495.0 | 1.098577637297511 | None | None |
| `midday60_mes_two_sided_nq_extension_reversion_1200` | limited_core_grid_test | 21/81 | 0 | 3100.0 | 1.083614295347269 | None | None |
| `morning15_mes_buy_nq_up_extension_short_1000` | limited_monkey_test | 59/81 | 34 | 17740.0 | 1.8666340986809966 | 0.838125 | 0.551375 |
| `morning15_mes_sell_nq_down_extension_long_1000` | limited_core_grid_test | 9/81 | 0 | 2380.0 | 1.1153659718856035 | None | None |

No variant reached WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance, or candidate reporting.

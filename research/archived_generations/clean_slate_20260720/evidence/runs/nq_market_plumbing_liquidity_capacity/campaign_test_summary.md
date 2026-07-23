# NQ Market Plumbing Liquidity Capacity Campaign Summary

Final verdict: FAIL.

All five predeclared NQ variants were run through the staged workflow. Two variants passed limited core but failed limited monkey. Three variants failed the limited core grid gate. No variant reached WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

| variant | terminal stage | core profitable combos | top net | top PF | top trades | top MAR | monkey profitable rate | monkey median net | monkey net beat | monkey DD beat |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| dealer_lending_pressure_long_1130 | limited_core_grid_test | 18/27 | 3035.0 | 1.2793373216751036 | 68 | 1.72930324703508 | None | None | None | None |
| dealer_lending_pressure_long_1330 | limited_monkey_test | 26/27 | 2795.0 | 1.373913043478261 | 68 | 2.587010955792933 | 0.431 | -550.0 | 0.7675 | 0.599875 |
| dual_pressure_priority_long_1130 | limited_monkey_test | 62/81 | 8225.0 | 1.4816983894582723 | 101 | 3.4196515191467642 | 0.4695 | -305.0 | 0.835 | 0.916625 |
| vx_oi_crowding_short_1330 | limited_core_grid_test | 0/27 | -1355.0 | 0.8535135135135136 | 79 | -0.5754850169492362 | None | None | None | None |
| vx_oi_stress_long_1330 | limited_core_grid_test | 17/27 | 4365.0 | 1.4968696642003414 | 60 | 1.7713765361054068 | None | None | None | None |

CSV detail: `backtest-campaigns/nq_market_plumbing_liquidity_capacity/campaign_results.csv`

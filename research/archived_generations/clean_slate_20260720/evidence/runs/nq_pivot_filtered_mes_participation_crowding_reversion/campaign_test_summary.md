# nq_pivot_filtered_mes_participation_crowding_reversion Campaign Test Summary

Date: 2026-06-22

Verdict: FAIL.

All five predeclared NQ pivot-filtered MES participation crowding variants failed the staged flow. Four failed `limited_core_grid_test`; `late_morning_trade_two_sided_reversal_window_1200` passed core but failed `limited_monkey_test` before WFA.

## Results

| variant_id | terminal_stage | profitable_combos | core_combos | top_net | top_pf | top_mar | top_trades | monkey_profitable | monkey_median_net | failure |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| morning_notional_down_reversal_long_window_1100 | limited_core_grid_test | 30 | 81 | 4140.0 | 1.1434511434511434 | 0.7513442714101858 | 49 |  |  | summary.percentage_profitable_iterations=0.37037037037037035 |
| morning_notional_two_sided_reversal_window_1130 | limited_core_grid_test | 53 | 81 | 10595.0 | 1.2707987220447283 | 2.8209336483706657 | 90 |  |  | summary.percentage_profitable_iterations=0.654320987654321 |
| late_morning_trade_two_sided_reversal_window_1200 | limited_monkey_test | 64 | 81 | 25940.0 | 1.7964384402824685 | 11.000667402259978 | 75 | 0.440375 | -1590.0 | summary.core_beats_monkey_net_profit_rate=0.813 |
| midday_notional_two_sided_reversal_window_1330 | limited_core_grid_test | 41 | 81 | 3025.0 | 1.0859985785358919 | 0.7186083703590154 | 107 |  |  | summary.percentage_profitable_iterations=0.5061728395061729 |
| afternoon_trade_two_sided_reversal_window_1500 | limited_core_grid_test | 45 | 81 | 21675.0 | 1.582191780821918 | 4.450068531684496 | 66 |  |  | summary.percentage_profitable_iterations=0.5555555555555556 |

## Rejection Rationale

- Core-only profitability was not stable enough for four variants. The afternoon and morning two-sided variants had positive top combinations, but only 45/81 and 53/81 profitable combinations respectively, below the 70% core stability gate.
- The density-adjusted morning long variant remained weak: 30/81 profitable combinations, zero benchmark-passing combinations, and the best row failed concentration controls.
- The strongest staged variant was `late_morning_trade_two_sided_reversal_window_1200`: 64/81 profitable core combinations, top net 25940.0, PF 1.7964, MAR 11.0007, but monkey robustness failed with `core_beats_monkey_net_profit_rate=0.813`, `percentage_profitable=0.440375`, and median net -1590.0.
- No variant reached WFA, WFA OOS monkey, WFA OOS Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.
- No post-result NQ rescue is authorized for this campaign.

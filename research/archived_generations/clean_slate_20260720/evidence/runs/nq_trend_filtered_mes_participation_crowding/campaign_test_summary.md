# nq_trend_filtered_mes_participation_crowding Campaign Test Summary

Date: 2026-06-22

Verdict: FAIL.

All five predeclared NQ trend-filtered MES participation variants failed the staged flow. Four variants failed `limited_core_grid_test`; `midday_notional_trend_pullback_reversal_1200` passed core but failed `limited_monkey_test` before WFA.

## Results

| variant_id | terminal_stage | profitable_combos | core_combos | top_net | top_pf | top_mar | top_trades | monkey_profitable | monkey_median_net | failure |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| afternoon_notional_trend_pullback_reversal_1400 | limited_core_grid_test | 0 | 81 | -2100.0 | 0.8368298368298368 | -1.2454244992438268 | 42 |  |  | summary.percentage_profitable_iterations=0.0 |
| early_afternoon_notional_trend_pullback_reversal_1300 | limited_core_grid_test | 51 | 81 | 6220.0 | 1.2949964429689353 | 1.2653874693647513 | 48 |  |  | summary.percentage_profitable_iterations=0.6296296296296297 |
| midday_notional_trend_pullback_reversal_1200 | limited_monkey_test | 72 | 81 | 7025.0 | 1.2636022514071295 | 1.8820010873579347 | 55 | 0.47025 | -540.0 | summary.core_beats_monkey_net_profit_rate=0.73625;summary.core_beats_monkey_max_drawdown_rate=0.624875 |
| morning_notional_trend_pullback_reversal_1030 | limited_core_grid_test | 15 | 81 | 8600.0 | 1.3015956514115379 | 1.2755348957794708 | 66 |  |  | summary.percentage_profitable_iterations=0.18518518518518517 |
| morning_trade_trend_pullback_reversal_1030 | limited_core_grid_test | 12 | 81 | 6250.0 | 1.1951905059337913 | 0.8167423634145805 | 69 |  |  | summary.percentage_profitable_iterations=0.14814814814814814 |

## Rejection Rationale

- The ES-like morning trade variant did not transfer to NQ: 12/81 profitable core combinations and top PF below the 1.2 benchmark.
- The strongest NQ variant was midday notional: 72/81 profitable core combinations, top net 7025.0, PF 1.2636, MAR 1.8820, but monkey robustness failed with `core_beats_monkey_net_profit_rate=0.73625`, `core_beats_monkey_max_drawdown_rate=0.624875`, `percentage_profitable=0.47025`, and median net -540.0.
- No variant reached WFA, WFA OOS monkey, WFA OOS Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.
- No rescue is authorized after these NQ results.

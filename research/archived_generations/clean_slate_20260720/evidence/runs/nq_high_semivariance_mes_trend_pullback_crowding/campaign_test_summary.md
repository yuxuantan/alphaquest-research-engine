# NQ High-Semivariance MES Crowding Campaign Summary

Final verdict: FAIL.

All five predeclared NQ variants were run through the staged workflow. Four failed the limited core grid gate. The afternoon 60-minute notional variant passed core but failed the limited monkey robustness gate, so no variant reached WFA, Monte Carlo, simulated incubation, acceptance, or candidate reporting.

| variant | terminal stage | core profitable combos | top net | top PF | top trades | top MAR | monkey profitable rate | monkey median net |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| afternoon60_notional_high_downside_window_1530 | limited_monkey_test | 41/54 | 23430.0 | 1.3248301677526688 | 92 | 2.981187504161886 | 0.468 | -1335.0 |
| late_morning30_notional_high_downside_window_1230 | limited_core_grid_test | 18/54 | 10165.0 | 1.1694449074845807 | 85 | 2.284271271231375 | None | None |
| midday60_notional_high_downside_window_1430 | limited_core_grid_test | 27/54 | 28687.5 | 1.3915847665847665 | 96 | 3.1871332779097465 | None | None |
| morning15_notional_high_downside_window_1130 | limited_core_grid_test | 2/54 | 3375.0 | 1.0466998754669987 | 86 | 0.3451071201246235 | None | None |
| morning15_trade_high_downside_window_1130 | limited_core_grid_test | 18/54 | 14750.0 | 1.2042653372109127 | 90 | 1.731962627036529 | None | None |

CSV detail: `backtest-campaigns/nq_high_semivariance_mes_trend_pullback_crowding/campaign_results.csv`

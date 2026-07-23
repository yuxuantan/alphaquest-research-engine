# nq_import_export_price_pressure Campaign Test Summary

Date: 2026-06-23

Verdict: FAIL.

All five predeclared NQ import/export price-pressure variants failed the clean `run1` staged flow. Four variants failed limited core with 0/18 profitable combinations. `core_pressure_large20_short_1200` passed limited core but failed monkey drawdown robustness, so no variant reached WFA, Monte Carlo, simulated incubation, acceptance, or candidate reporting.

## Results

| variant_id | terminal_stage | profitable_combos | core_combos | top_net | top_pf | top_mar | top_trades | monkey_profitable | monkey_median_net | net_beat | dd_beat | failure |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| core_pressure_large20_short_1200 | limited_monkey_test | 17 | 18 | 3075.0 | 1.4479242534595775 | 1.464508051975513 | 72 | 0.25325 | -1355.0 | 0.93075 | 0.7755 | summary.core_beats_monkey_max_drawdown_rate=0.7755 |
| core_pressure_signed_short_1100 | limited_core_grid_test | 0 | 18 | -2282.5 | 0.7926884650317892 | -0.5652662647565225 | 95 |  |  |  |  | summary.percentage_profitable_iterations=0.0 |
| import_disinflation_large20_long_1200 | limited_core_grid_test | 0 | 18 | -1005.0 | 0.833195020746888 | -0.7116376389839545 | 71 |  |  |  |  | summary.percentage_profitable_iterations=0.0 |
| import_disinflation_large20_long_1430 | limited_core_grid_test | 0 | 18 | -455.0 | 0.9136622390891841 | -0.16629355398209925 | 75 |  |  |  |  | summary.percentage_profitable_iterations=0.0 |
| import_disinflation_signed_long_1030 | limited_core_grid_test | 0 | 18 | -987.5 | 0.8934735706580367 | -0.4779032838623781 | 85 |  |  |  |  | summary.percentage_profitable_iterations=0.0 |

## Rejection Rationale

- The direct ES-rescue port initially failed pre-PnL NQ signal density; a logged density-only pre-PnL reform cleared the density gate before any NQ PnL was evaluated.
- Four variants then failed limited core with 0/18 profitable combinations, so the macro/orderflow edge did not survive basic parameter-neighborhood stability.
- `core_pressure_large20_short_1200` had 17/18 profitable core combinations and top core net 3075.0, but failed monkey drawdown robustness: drawdown beat rate 0.7755 versus the 0.90 gate, despite net beat rate 0.93075.
- No post-result NQ rescue is authorized for this campaign, and no `candidate_strategy_report.md` was created.

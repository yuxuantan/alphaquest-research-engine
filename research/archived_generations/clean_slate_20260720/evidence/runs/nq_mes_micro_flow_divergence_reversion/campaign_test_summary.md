# nq_mes_micro_flow_divergence_reversion Campaign Test Summary

Date: 2026-06-22

Verdict: FAIL.

All five predeclared NQ MES micro-flow divergence variants failed the clean `run2` staged flow. `run1` is ignored for result rollup because it halted before testing on an unsupported descriptive `data.feature_set` value.

## Results

| variant_id | terminal_stage | profitable_combos | core_combos | top_net | top_pf | top_mar | top_trades | monkey_profitable | monkey_median_net | net_beat | dd_beat | failure |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| afternoon_mes_large20_buy_pressure_short | limited_core_grid_test | 0 | 36 | -5040.0 | 0.7580993520518359 | -0.6250049282990565 | 39 |  |  |  |  | summary.percentage_profitable_iterations=0.0 |
| afternoon_mes_large20_sell_pressure_long | limited_monkey_test | 29 | 36 | 12980.0 | 2.2967032967032965 | 6.723408664109506 | 27 | 0.49075 | -177.5 | 0.921125 | 0.858 | summary.core_beats_monkey_max_drawdown_rate=0.858 |
| midday_mes_price_richness_fade | limited_monkey_test | 36 | 36 | 17775.0 | 1.2305746530029835 | 2.6406505835987657 | 174 | 0.4585 | -2477.5 | 0.845125 | 0.835375 | summary.core_beats_monkey_net_profit_rate=0.845125;summary.core_beats_monkey_max_drawdown_rate=0.835375 |
| morning_mes_buy_pressure_reversion_short | limited_monkey_test | 28 | 36 | 22815.0 | 1.5333099579242637 | 4.800686626427652 | 75 | 0.49525 | -95.0 | 0.80825 | 0.630625 | summary.core_beats_monkey_net_profit_rate=0.80825;summary.core_beats_monkey_max_drawdown_rate=0.630625 |
| morning_mes_sell_pressure_reversion_long | limited_core_grid_test | 9 | 36 | 4680.0 | 1.1720588235294118 | 1.0819836932785505 | 65 |  |  |  |  | summary.percentage_profitable_iterations=0.25 |

## Rejection Rationale

- `afternoon_mes_large20_buy_pressure_short` had 0/36 profitable core combinations and failed immediately on the 70% profitable-iteration gate.
- `morning_mes_sell_pressure_reversion_long` had only 9/36 profitable core combinations despite a positive top row, so the result was not broad enough to justify promotion.
- `afternoon_mes_large20_sell_pressure_long`, `midday_mes_price_richness_fade`, and `morning_mes_buy_pressure_reversion_short` passed core but failed monkey robustness. Median monkey net profit was negative for all three, and at least one required net-profit or drawdown beat-rate gate failed in each case.
- No variant reached WFA, WFA OOS monkey, WFA OOS Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.
- No post-result NQ rescue is authorized for this campaign.
- Data caveat remains material: MES is a cross-index micro-flow proxy for NQ, not native MNQ orderflow.

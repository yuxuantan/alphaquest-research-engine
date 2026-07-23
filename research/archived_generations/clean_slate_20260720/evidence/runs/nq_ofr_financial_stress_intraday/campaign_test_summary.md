# nq_ofr_financial_stress_intraday Campaign Test Summary

Date: 2026-06-22

Verdict: FAIL.

All five predeclared NQ OFR financial-stress variants failed the clean `run1` staged flow. High-credit stress reached WFA but failed out-of-sample; no variant reached OOS monkey, Monte Carlo, simulated incubation, acceptance, or candidate reporting.

## Results

| variant_id | terminal_stage | profitable_combos | core_combos | top_net | top_pf | top_mar | top_trades | monkey_profitable | monkey_median_net | net_beat | dd_beat | wfa_net | wfa_pf | wfa_mar | failure |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| funding_stress_short_1130 | limited_core_grid_test | 18 | 27 | 1815.0 | 1.1019949423995505 | 1.2461158256899854 | 132 |  |  |  |  |  |  |  | summary.percentage_profitable_iterations=0.6666666666666666 |
| high_credit_stress_short_1030 | walk_forward_analysis | 24 | 27 | 6395.0 | 1.2438977879481312 | 2.726189359077553 | 183 | 0.11675 | -4855.0 | 0.984375 | 0.975625 | -6597.5 | 0.8701151688158283 | -0.5403656917695282 | summary.early_exit=True;stitched_oos_metrics.profit_factor=0.8701151688158283;stitched_oos_metrics.mar=-0.5403656917695282 |
| rising_global_stress_short_1000 | limited_core_grid_test | 15 | 27 | 2195.0 | 1.1250712250712251 | 0.308575950277386 | 105 |  |  |  |  |  |  |  | summary.percentage_profitable_iterations=0.5555555555555556 |
| us_stress_short_1200 | limited_core_grid_test | 18 | 27 | 2455.0 | 1.1315648445873527 | 1.1523439656441306 | 137 |  |  |  |  |  |  |  | summary.percentage_profitable_iterations=0.6666666666666666 |
| volatility_stress_short_1330 | limited_monkey_test | 24 | 27 | 2762.5 | 1.279888551165147 | 2.2840202686828213 | 94 | 0.1875 | -2075.0 | 0.906375 | 0.655125 |  |  |  | summary.core_beats_monkey_max_drawdown_rate=0.655125 |

## Rejection Rationale

- Funding, rising-global, and U.S. stress failed the 70% core profitable-iteration stability gate.
- Volatility stress passed core but failed monkey robustness: profitable monkey rate 0.1875, median net -2075.0, drawdown beat rate 0.655125.
- High-credit stress passed core and monkey but failed WFA: early_exit=true, stitched OOS net -6597.5, PF 0.8701, MAR -0.5404.
- No post-result NQ rescue is authorized for this campaign.

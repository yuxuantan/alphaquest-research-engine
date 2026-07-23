# nq_spx_0dte_trend_aligned_pressure Campaign Test Summary

Date: 2026-06-22

Verdict: FAIL.

All five predeclared NQ SPX 0DTE trend-aligned variants failed `limited_core_grid_test` in the clean `run1` staged flow. The pre-PnL density audit passed, but after costs every core-grid combination was net unprofitable.

## Results

| variant_id | terminal_stage | profitable_combos | core_combos | top_net | top_pf | top_mar | top_trades | top_trades_per_year | failure |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| all_0dte_trend_continuation_1330 | limited_core_grid_test | 0 | 36 | -705.0 | 0.8173575129533679 | -0.3765483359940463 | 34 | 35.47122355671483 | summary.percentage_profitable_iterations=0.0 |
| all_0dte_trend_continuation_1400 | limited_core_grid_test | 0 | 12 | -135.0 | 0.9425531914893617 | -0.19588522508090186 | 39 | 42.38694199403636 | summary.percentage_profitable_iterations=0.0 |
| all_0dte_trend_continuation_1500 | limited_core_grid_test | 0 | 9 | -35.0 | 0.9772727272727273 | -0.056175653781745265 | 28 | 29.554540984758024 | summary.percentage_profitable_iterations=0.0 |
| all_0dte_trend_only_1330 | limited_core_grid_test | 0 | 12 | -805.0 | 0.7967171717171717 | -0.40913224580327223 | 35 | 36.51449483779468 | summary.percentage_profitable_iterations=0.0 |
| all_0dte_trend_only_1500 | limited_core_grid_test | 0 | 3 | -270.0 | 0.8741258741258742 | -0.4078324010357951 | 39 | 38.80999366172533 | summary.total_combinations_tested=3;summary.percentage_profitable_iterations=0.0 |

## Rejection Rationale

- Every variant had 0 profitable core-grid combinations after NQ costs and pessimistic fill assumptions.
- The best core row was still net negative: `all_0dte_trend_continuation_1500` had top net -35.0 and PF 0.9773.
- No variant reached monkey robustness, WFA, WFA OOS monkey, WFA OOS Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.
- No post-result NQ rescue is authorized for this campaign.

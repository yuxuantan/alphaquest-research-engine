# NQ Round-Number Orderflow Barrier Campaign Test Summary

Verdict: FAIL

All five predeclared NQ round-number orderflow barrier variants failed limited_core_grid_test. Best variant-level profitable rate was 24/54 = 0.444444, below the required 0.70 threshold. Across 270 official combinations, 54 were profitable, 37 passed benchmark rows, and 0 had Apex rule violations. Positive top rows are rejected as unstable neighboring-parameter pockets, not candidate strategies.

## Gate Outcome

- Terminal stage: limited_core_grid_test
- Variants tested: 5
- Variants passed: 0
- Official combinations tested: 270
- Profitable combinations: 54 (0.200000)
- Benchmark-passing combinations: 37
- Apex rule violating iterations: 0
- Downstream stages reached: none

## Variant Results

| Variant | Profitable combos | Profitable rate | Benchmark pass combos | Top net | Top PF | Top MAR | Top trades | Top failure reason |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| morning_support_sell_absorption_long | 24/54 | 0.444444 | 15 | 2865.0 | 1.2462397937258272 | 0.7097760302991206 | 123 |  |
| morning_resistance_buy_absorption_short | 1/54 | 0.018519 | 0 | 345.0 | 1.023695054945055 | 0.11155647083685886 | 126 | max_best_day_concentration |
| midday_two_sided_large10_absorption_reclaim | 0/54 | 0.000000 | 0 | -190.0 | 0.9882425742574258 | -0.033737189093102644 | 176 | min_total_net_profit;max_consecutive_losses |
| round_number_upside_flow_breakout_long | 5/54 | 0.092593 | 0 | 545.0 | 1.0731543624161073 | 0.1889054763004475 | 97 | max_consecutive_losses;max_best_day_concentration |
| round_number_downside_flow_breakout_short | 24/54 | 0.444444 | 22 | 3225.0 | 1.178029257521391 | 1.2537391682650443 | 187 |  |

## Rejection Note

The support-long and downside-breakout variants had profitable top rows, but the official gate requires parameter-neighborhood stability. Both reached only 24 profitable rows out of 54, so narrowing to the top rows would be post-result selection.

No candidate_strategy_report.md was created because nothing reached WFA, Monte Carlo, simulated incubation, or acceptance OOS.

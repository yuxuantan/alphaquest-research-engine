# Campaign Test Summary

- Campaign: `es_true_vap_aoi_breakout_continuation`
- Variant: `prior_extreme_large10_true_vap_two_sided_1500`
- Timeframe: `1m`
- Overall passed: `False`

| Stage | Status | Failed Criteria |
|---|---:|---|
| Limited Core Grid Test | error | summary.total_combinations_tested actual=None expected={'valid_parameter_combination_count': '1 fixed combo or 8-120 tunable combos'}<br>summary.percentage_profitable_iterations actual=None expected={'min': 0.7}<br>'int' object has no attribute 'split' |
| Limited Monkey Test | skipped | prior stage failed |
| Walk Forward Analysis (WFA) | skipped | prior stage failed |
| WFA OOS Monkey Test | skipped | prior stage failed |
| WFA OOS Monte Carlo | skipped | prior stage failed |
| Simulated Incubation (OOS) Core | skipped | prior stage failed |
| Simulated Incubation (OOS) Monkey | skipped | prior stage failed |
| Acceptance OOS Test | skipped | prior stage failed |

# Campaign Test Summary

- Campaign: `es_treasury_auction_pressure`
- Variant: `all_coupon_late_reversal_long_1430`
- Timeframe: `1m`
- Overall passed: `False`

| Stage | Status | Failed Criteria |
|---|---:|---|
| Limited Core Grid Test | failed | summary.total_combinations_tested actual=3 expected={'valid_parameter_combination_count': '1 fixed combo or 8-120 tunable combos'}<br>summary.percentage_profitable_iterations actual=0.0 expected={'min': 0.7} |
| Limited Monkey Test | skipped | prior stage failed |
| Walk Forward Analysis (WFA) | skipped | prior stage failed |
| WFA OOS Monkey Test | skipped | prior stage failed |
| WFA OOS Monte Carlo | skipped | prior stage failed |
| Simulated Incubation (OOS) Core | skipped | prior stage failed |
| Simulated Incubation (OOS) Monkey | skipped | prior stage failed |
| Acceptance OOS Test | skipped | prior stage failed |

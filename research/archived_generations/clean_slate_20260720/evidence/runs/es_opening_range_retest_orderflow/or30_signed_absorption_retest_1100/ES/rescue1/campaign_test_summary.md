# Campaign Test Summary

- Campaign: `es_opening_range_retest_orderflow`
- Variant: `or30_signed_absorption_retest_1100`
- Timeframe: `5m`
- Overall passed: `False`

| Stage | Status | Failed Criteria |
|---|---:|---|
| Limited Core Grid Test | failed | summary.percentage_profitable_iterations actual=0.012345679012345678 expected={'min': 0.7} |
| Limited Monkey Test | skipped | prior stage failed |
| Walk Forward Analysis (WFA) | skipped | prior stage failed |
| WFA OOS Monkey Test | skipped | prior stage failed |
| WFA OOS Monte Carlo | skipped | prior stage failed |
| Simulated Incubation (OOS) Core | skipped | prior stage failed |
| Simulated Incubation (OOS) Monkey | skipped | prior stage failed |
| Acceptance OOS Test | skipped | prior stage failed |

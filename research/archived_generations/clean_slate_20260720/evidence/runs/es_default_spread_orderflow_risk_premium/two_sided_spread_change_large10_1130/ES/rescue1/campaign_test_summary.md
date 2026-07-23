# Campaign Test Summary

- Campaign: `es_default_spread_orderflow_risk_premium`
- Variant: `two_sided_spread_change_large10_1130`
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

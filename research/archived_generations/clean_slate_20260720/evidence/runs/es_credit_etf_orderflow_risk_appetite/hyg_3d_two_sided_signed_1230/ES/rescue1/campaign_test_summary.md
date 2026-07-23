# Campaign Test Summary

- Campaign: `es_credit_etf_orderflow_risk_appetite`
- Variant: `hyg_3d_two_sided_signed_1230`
- Timeframe: `5m`
- Overall passed: `False`

| Stage | Status | Failed Criteria |
|---|---:|---|
| Limited Core Grid Test | passed |  |
| Limited Monkey Test | passed |  |
| Walk Forward Analysis (WFA) | failed | stitched_oos_metrics.profit_factor actual=1.077365644773513 expected={'min': 1.2}<br>stitched_oos_metrics.mar actual=0.08981641818942494 expected={'min': 0.4} |
| WFA OOS Monkey Test | skipped | prior stage failed |
| WFA OOS Monte Carlo | skipped | prior stage failed |
| Simulated Incubation (OOS) Core | skipped | prior stage failed |
| Simulated Incubation (OOS) Monkey | skipped | prior stage failed |
| Acceptance OOS Test | skipped | prior stage failed |

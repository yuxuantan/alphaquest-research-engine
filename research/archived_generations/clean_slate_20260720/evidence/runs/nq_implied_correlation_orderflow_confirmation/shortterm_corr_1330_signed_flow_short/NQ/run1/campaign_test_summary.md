# Campaign Test Summary

- Campaign: `nq_implied_correlation_orderflow_confirmation`
- Variant: `shortterm_corr_1330_signed_flow_short`
- Timeframe: `1m`
- Overall passed: `False`

| Stage | Status | Failed Criteria |
|---|---:|---|
| Limited Core Grid Test | passed |  |
| Limited Monkey Test | passed |  |
| Walk Forward Analysis (WFA) | failed | stitched_oos_metrics.profit_factor actual=0.8877429905309524 expected={'min': 1.2}<br>stitched_oos_metrics.mar actual=-0.062208940108462375 expected={'min': 0.4} |
| WFA OOS Monkey Test | skipped | prior stage failed |
| WFA OOS Monte Carlo | skipped | prior stage failed |
| Simulated Incubation (OOS) Core | skipped | prior stage failed |
| Simulated Incubation (OOS) Monkey | skipped | prior stage failed |
| Acceptance OOS Test | skipped | prior stage failed |

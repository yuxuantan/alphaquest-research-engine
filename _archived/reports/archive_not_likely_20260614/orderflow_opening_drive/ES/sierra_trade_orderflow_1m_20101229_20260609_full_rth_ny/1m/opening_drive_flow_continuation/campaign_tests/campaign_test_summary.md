# Campaign Test Summary

- Campaign: `orderflow_opening_drive`
- Variant: `opening_drive_flow_continuation`
- Timeframe: `1m`
- Overall passed: `False`

| Stage | Status | Failed Criteria |
|---|---:|---|
| Walk Forward Analysis (WFA) | failed | stitched_oos_metrics.profit_factor actual=1.0042059909725072 expected={'min': 1.4}<br>stitched_oos_metrics.mar actual=0.0020356537025288906 expected={'min': 0.5}<br>stitched_oos_metrics.expectancy_r actual=0.0057276573026019545 expected={'min': 0.2}<br>stitched_oos_metrics.total_trades actual=162 expected={'min': 500} |
| WFA OOS Monkey Test | skipped | prior stage failed |
| WFA OOS Monte Carlo | skipped | prior stage failed |
| Simulated Incubation (OOS) Core | skipped | prior stage failed |
| Simulated Incubation (OOS) Monkey | skipped | prior stage failed |

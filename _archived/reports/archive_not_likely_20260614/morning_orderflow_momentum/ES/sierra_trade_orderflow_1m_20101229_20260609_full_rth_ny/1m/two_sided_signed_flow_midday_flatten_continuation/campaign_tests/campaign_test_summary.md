# Campaign Test Summary

- Campaign: `morning_orderflow_momentum`
- Variant: `two_sided_signed_flow_midday_flatten_continuation`
- Timeframe: `1m`
- Overall passed: `False`

| Stage | Status | Failed Criteria |
|---|---:|---|
| Limited Core Grid Test | passed |  |
| Limited Monkey Test | passed |  |
| Walk Forward Analysis (WFA) | failed | summary.early_exit actual=True expected={'equals': False}<br>summary.windows actual=1 expected={'min': 10}<br>stitched_oos_metrics.profit_factor actual=0.0 expected={'min': 1.4}<br>stitched_oos_metrics.mar actual=0.0 expected={'min': 0.5}<br>stitched_oos_metrics.expectancy_r actual=0.0 expected={'min': 0.2}<br>stitched_oos_metrics.total_trades actual=0 expected={'min': 500} |
| WFA OOS Monkey Test | skipped | prior stage failed |
| WFA OOS Monte Carlo | skipped | prior stage failed |
| Simulated Incubation (OOS) Core | skipped | prior stage failed |
| Simulated Incubation (OOS) Monkey | skipped | prior stage failed |

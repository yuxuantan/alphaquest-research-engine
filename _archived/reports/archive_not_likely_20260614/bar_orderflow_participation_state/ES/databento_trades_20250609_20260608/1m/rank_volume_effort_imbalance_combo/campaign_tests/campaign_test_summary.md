# Campaign Test Summary

- Campaign: `bar_orderflow_participation_state`
- Variant: `rank_volume_effort_imbalance_combo`
- Timeframe: `1m`
- Overall passed: `False`

| Stage | Status | Failed Criteria |
|---|---:|---|
| Limited Core Grid Test | passed |  |
| Limited Monkey Test | passed |  |
| Walk Forward Analysis (WFA) | failed | summary.windows actual=8 expected={'min': 10}<br>stitched_oos_metrics.expectancy_r actual=0.07635822811679525 expected={'min': 0.2}<br>stitched_oos_metrics.total_trades actual=95 expected={'min': 500} |
| WFA OOS Monkey Test | skipped | prior stage failed |
| WFA OOS Monte Carlo | skipped | prior stage failed |
| Simulated Incubation (OOS) Core | skipped | prior stage failed |
| Simulated Incubation (OOS) Monkey | skipped | prior stage failed |

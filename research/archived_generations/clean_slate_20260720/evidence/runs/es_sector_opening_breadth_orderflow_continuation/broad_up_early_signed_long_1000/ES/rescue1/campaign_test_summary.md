# Campaign Test Summary

- Campaign: `es_sector_opening_breadth_orderflow_continuation`
- Variant: `broad_up_early_signed_long_1000`
- Timeframe: `5m`
- Overall passed: `False`

| Stage | Status | Failed Criteria |
|---|---:|---|
| Limited Core Grid Test | passed |  |
| Limited Monkey Test | passed |  |
| Walk Forward Analysis (WFA) | failed | summary.early_exit actual=True expected={'equals': False}<br>stitched_oos_metrics.profit_factor actual=0.9644457723334329 expected={'min': 1.2}<br>stitched_oos_metrics.mar actual=-0.09285370075346508 expected={'min': 0.4}<br>stitched_oos_metrics.trades_per_year actual=42.94343950778083 expected={'min': 50} |
| WFA OOS Monkey Test | skipped | prior stage failed |
| WFA OOS Monte Carlo | skipped | prior stage failed |
| Simulated Incubation (OOS) Core | skipped | prior stage failed |
| Simulated Incubation (OOS) Monkey | skipped | prior stage failed |
| Acceptance OOS Test | skipped | prior stage failed |

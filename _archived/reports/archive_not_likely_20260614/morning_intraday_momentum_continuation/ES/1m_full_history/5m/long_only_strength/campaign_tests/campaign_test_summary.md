# Campaign Test Summary

- Campaign: `morning_intraday_momentum_continuation`
- Variant: `long_only_strength`
- Timeframe: `5m`
- Overall passed: `False`

| Stage | Status | Failed Criteria |
|---|---:|---|
| Limited Core Grid Test | passed |  |
| Limited Monkey Test | passed |  |
| Walk Forward Analysis (WFA) | failed | stitched_oos_metrics.profit_factor actual=1.1161986954741143 expected={'min': 1.5}<br>stitched_oos_metrics.mar actual=0.21527684239354794 expected={'min': 1.5}<br>stitched_oos_metrics.expectancy_r actual=0.0559962732823321 expected={'min': 0.2} |
| WFA OOS Monkey Test | skipped | prior stage failed |
| WFA OOS Monte Carlo | skipped | prior stage failed |
| Simulated Incubation (OOS) Core | skipped | prior stage failed |
| Simulated Incubation (OOS) Monkey | skipped | prior stage failed |

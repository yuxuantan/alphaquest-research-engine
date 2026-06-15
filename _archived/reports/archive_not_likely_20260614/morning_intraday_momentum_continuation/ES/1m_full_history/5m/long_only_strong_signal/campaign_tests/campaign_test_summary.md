# Campaign Test Summary

- Campaign: `morning_intraday_momentum_continuation`
- Variant: `long_only_strong_signal`
- Timeframe: `5m`
- Overall passed: `False`

| Stage | Status | Failed Criteria |
|---|---:|---|
| Limited Core Grid Test | passed |  |
| Limited Monkey Test | passed |  |
| Walk Forward Analysis (WFA) | failed | stitched_oos_metrics.profit_factor actual=1.1048656723496075 expected={'min': 1.5}<br>stitched_oos_metrics.mar actual=0.1946751320299451 expected={'min': 1.5}<br>stitched_oos_metrics.expectancy_r actual=0.059970042761921354 expected={'min': 0.2}<br>stitched_oos_metrics.total_trades actual=413 expected={'min': 500} |
| WFA OOS Monkey Test | skipped | prior stage failed |
| WFA OOS Monte Carlo | skipped | prior stage failed |
| Simulated Incubation (OOS) Core | skipped | prior stage failed |
| Simulated Incubation (OOS) Monkey | skipped | prior stage failed |

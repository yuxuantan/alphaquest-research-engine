# Campaign Test Summary

- Campaign: `nq_impulse_pause_orderflow_continuation`
- Variant: `late_morning_large10_two_sided_impulse_pause_breakout_1230`
- Timeframe: `5m`
- Overall passed: `False`

| Stage | Status | Failed Criteria |
|---|---:|---|
| Limited Core Grid Test | passed |  |
| Limited Monkey Test | passed |  |
| Walk Forward Analysis (WFA) | failed | stitched_oos_metrics.profit_factor actual=1.0910835460066868 expected={'min': 1.2}<br>stitched_oos_metrics.mar actual=0.24920508009264916 expected={'min': 0.4} |
| WFA OOS Monkey Test | skipped | prior stage failed |
| WFA OOS Monte Carlo | skipped | prior stage failed |
| Simulated Incubation (OOS) Core | skipped | prior stage failed |
| Simulated Incubation (OOS) Monkey | skipped | prior stage failed |
| Acceptance OOS Test | skipped | prior stage failed |

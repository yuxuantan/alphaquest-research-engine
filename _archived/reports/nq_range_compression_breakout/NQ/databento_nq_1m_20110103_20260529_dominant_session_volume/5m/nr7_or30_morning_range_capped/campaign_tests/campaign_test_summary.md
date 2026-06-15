# Campaign Test Summary

- Campaign: `nq_range_compression_breakout`
- Variant: `nr7_or30_morning_range_capped`
- Timeframe: `5m`
- Overall passed: `False`

| Stage | Status | Failed Criteria |
|---|---:|---|
| Limited Core Grid Test | passed |  |
| Limited Monkey Test | passed |  |
| Walk Forward Analysis (WFA) | passed |  |
| WFA OOS Monkey Test | passed |  |
| WFA OOS Monte Carlo | failed | summary.probability_profit_before_drawdown actual=0.39 expected={'exclusive_min': 0.5} |
| Simulated Incubation (OOS) Core | skipped | prior stage failed |
| Simulated Incubation (OOS) Monkey | skipped | prior stage failed |
| Acceptance OOS Test | skipped | prior stage failed |

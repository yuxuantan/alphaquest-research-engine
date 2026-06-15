# Campaign Test Summary

- Campaign: `nq_morning_strength_continuation`
- Variant: `long_only_1030_strength_balanced_drive_probe`
- Timeframe: `5m`
- Overall passed: `False`

| Stage | Status | Failed Criteria |
|---|---:|---|
| Limited Core Grid Test | passed |  |
| Limited Monkey Test | passed |  |
| Walk Forward Analysis (WFA) | passed |  |
| WFA OOS Monkey Test | passed |  |
| WFA OOS Monte Carlo | failed | summary.probability_profit_before_drawdown actual=0.156 expected={'exclusive_min': 0.5} |
| Simulated Incubation (OOS) Core | skipped | prior stage failed |
| Simulated Incubation (OOS) Monkey | skipped | prior stage failed |
| Acceptance OOS Test | skipped | prior stage failed |

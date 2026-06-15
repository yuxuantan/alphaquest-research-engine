# Campaign Test Summary

- Campaign: `nq_intraday_momentum_priority`
- Variant: `short_first_1030_weakness_1130_strength`
- Timeframe: `5m`
- Overall passed: `False`

| Stage | Status | Failed Criteria |
|---|---:|---|
| Limited Core Grid Test | passed |  |
| Limited Monkey Test | passed |  |
| Walk Forward Analysis (WFA) | passed |  |
| WFA OOS Monkey Test | passed |  |
| WFA OOS Monte Carlo | passed |  |
| Simulated Incubation (OOS) Core | failed | metrics.expectancy_r actual=0.140262391429876 expected={'min': 0.15} |
| Simulated Incubation (OOS) Monkey | skipped | prior stage failed |

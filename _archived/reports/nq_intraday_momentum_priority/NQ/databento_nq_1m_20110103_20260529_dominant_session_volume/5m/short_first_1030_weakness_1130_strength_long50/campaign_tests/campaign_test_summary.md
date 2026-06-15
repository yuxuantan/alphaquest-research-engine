# Campaign Test Summary

- Campaign: `nq_intraday_momentum_priority`
- Variant: `short_first_1030_weakness_1130_strength_long50`
- Timeframe: `5m`
- Overall passed: `False`

| Stage | Status | Failed Criteria |
|---|---:|---|
| Limited Core Grid Test | passed |  |
| Limited Monkey Test | passed |  |
| Walk Forward Analysis (WFA) | passed |  |
| WFA OOS Monkey Test | passed |  |
| WFA OOS Monte Carlo | passed |  |
| Simulated Incubation (OOS) Core | passed |  |
| Simulated Incubation (OOS) Monkey | passed |  |
| Acceptance OOS Test | failed | metrics.profit_factor actual=0.8358413738160574 expected={'min': 1.0}<br>metrics.mar actual=-1.011726207063023 expected={'min': 1.0} |

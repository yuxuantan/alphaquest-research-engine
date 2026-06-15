# Campaign Test Summary

- Campaign: `morning_orderflow_momentum`
- Variant: `two_sided_signed_flow_1515_flatten_continuation`
- Timeframe: `1m`
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
| Acceptance OOS Test | failed | metrics.profit_factor actual=0.8631798747141295 expected={'min': 1.0}<br>metrics.mar actual=-1.1086973404413312 expected={'min': 1.0} |

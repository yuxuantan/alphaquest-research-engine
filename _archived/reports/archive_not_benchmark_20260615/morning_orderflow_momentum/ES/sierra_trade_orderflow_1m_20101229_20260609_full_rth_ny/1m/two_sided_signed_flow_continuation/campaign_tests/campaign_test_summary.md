# Campaign Test Summary

- Campaign: `morning_orderflow_momentum`
- Variant: `two_sided_signed_flow_continuation`
- Timeframe: `1m`
- Overall passed: `False`

| Stage | Status | Failed Criteria |
|---|---:|---|
| Limited Core Grid Test | passed |  |
| Limited Monkey Test | failed | summary.core_beats_monkey_max_drawdown_rate actual=0.748 expected={'min': 0.9} |
| Walk Forward Analysis (WFA) | passed |  |
| WFA OOS Monkey Test | passed |  |
| WFA OOS Monte Carlo | passed |  |
| Simulated Incubation (OOS) Core | failed | metrics.mar actual=0.944615760072713 expected={'min': 1.0} |
| Simulated Incubation (OOS) Monkey | failed | summary.core_beats_monkey_net_profit_rate actual=0.772 expected={'min': 0.8} |

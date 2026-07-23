# Campaign Test Summary

- Campaign: `es_cboe_vix_term_structure_intraday`
- Variant: `contango_long_1030`
- Timeframe: `1m`
- Overall passed: `False`

| Stage | Status | Failed Criteria |
|---|---:|---|
| Limited Core Grid Test | passed |  |
| Limited Monkey Test | failed | summary.core_beats_monkey_net_profit_rate actual=0.859625 expected={'min': 0.9}<br>summary.core_beats_monkey_max_drawdown_rate actual=0.7755 expected={'min': 0.9} |
| Walk Forward Analysis (WFA) | skipped | prior stage failed |
| WFA OOS Monkey Test | skipped | prior stage failed |
| WFA OOS Monte Carlo | skipped | prior stage failed |
| Simulated Incubation (OOS) Core | skipped | prior stage failed |
| Simulated Incubation (OOS) Monkey | skipped | prior stage failed |
| Acceptance OOS Test | skipped | prior stage failed |

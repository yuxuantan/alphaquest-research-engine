# Campaign Test Summary

- Campaign: `mes_es_flow_divergence_reversion`
- Variant: `afternoon_mes_large20_buy_pressure_short`
- Timeframe: `1m`
- Overall passed: `False`

| Stage | Status | Failed Criteria |
|---|---:|---|
| Limited Core Grid Test | passed |  |
| Limited Monkey Test | passed |  |
| Walk Forward Analysis (WFA) | failed | summary.windows actual=8 expected={'min': 10}<br>stitched_oos_metrics.total_trades actual=31 expected={'min': 500} |
| WFA OOS Monkey Test | skipped | prior stage failed |
| WFA OOS Monte Carlo | skipped | prior stage failed |
| Simulated Incubation (OOS) Core | skipped | prior stage failed |
| Simulated Incubation (OOS) Monkey | skipped | prior stage failed |

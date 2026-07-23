# Campaign Test Summary

- Campaign: `es_trend_filtered_mes_participation_crowding`
- Variant: `morning_trade_trend_pullback_reversal_1030`
- Timeframe: `1m`
- Overall passed: `False`

| Stage | Status | Failed Criteria |
|---|---:|---|
| Limited Core Grid Test | passed |  |
| Limited Monkey Test | passed |  |
| Walk Forward Analysis (WFA) | passed |  |
| WFA OOS Monkey Test | passed |  |
| WFA OOS Monte Carlo | passed |  |
| Simulated Incubation (OOS) Core | failed | metrics.profit_factor actual=0.6367792072095605 expected={'min': 1.0}<br>metrics.mar actual=-0.7926183684438697 expected={'min': 1.0} |
| Simulated Incubation (OOS) Monkey | skipped | prior stage failed |
| Acceptance OOS Test | skipped | prior stage failed |

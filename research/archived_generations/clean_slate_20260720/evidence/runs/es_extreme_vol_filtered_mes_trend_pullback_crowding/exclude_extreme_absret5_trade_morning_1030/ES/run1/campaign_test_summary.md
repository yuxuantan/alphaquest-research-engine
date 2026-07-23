# Campaign Test Summary

- Campaign: `es_extreme_vol_filtered_mes_trend_pullback_crowding`
- Variant: `exclude_extreme_absret5_trade_morning_1030`
- Timeframe: `1m`
- Overall passed: `False`

| Stage | Status | Failed Criteria |
|---|---:|---|
| Limited Core Grid Test | passed |  |
| Limited Monkey Test | passed |  |
| Walk Forward Analysis (WFA) | passed |  |
| WFA OOS Monkey Test | passed |  |
| WFA OOS Monte Carlo | passed |  |
| Simulated Incubation (OOS) Core | failed | metrics.profit_factor actual=0.6568509233991242 expected={'min': 1.0}<br>metrics.mar actual=-0.7864245825477231 expected={'min': 1.0} |
| Simulated Incubation (OOS) Monkey | skipped | prior stage failed |
| Acceptance OOS Test | skipped | prior stage failed |

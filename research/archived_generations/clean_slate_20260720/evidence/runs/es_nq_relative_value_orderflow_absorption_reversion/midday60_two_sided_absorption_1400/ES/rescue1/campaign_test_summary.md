# Campaign Test Summary

- Campaign: `es_nq_relative_value_orderflow_absorption_reversion`
- Variant: `midday60_two_sided_absorption_1400`
- Timeframe: `1m`
- Overall passed: `False`

| Stage | Status | Failed Criteria |
|---|---:|---|
| Limited Core Grid Test | passed |  |
| Limited Monkey Test | passed |  |
| Walk Forward Analysis (WFA) | failed | summary.early_exit actual=True expected={'equals': False}<br>stitched_oos_metrics.profit_factor actual=0.7169466764061359 expected={'min': 1.2}<br>stitched_oos_metrics.mar actual=-0.6975521321854036 expected={'min': 0.4}<br>stitched_oos_metrics.trades_per_year actual=40.80309072008192 expected={'min': 50} |
| WFA OOS Monkey Test | skipped | prior stage failed |
| WFA OOS Monte Carlo | skipped | prior stage failed |
| Simulated Incubation (OOS) Core | skipped | prior stage failed |
| Simulated Incubation (OOS) Monkey | skipped | prior stage failed |
| Acceptance OOS Test | skipped | prior stage failed |

# Campaign Test Summary

- Campaign: `nq_intraday_capitulation_mean_reversion`
- Variant: `midday_15m_vwap_flush_reclaim_long_1430`
- Timeframe: `1m`
- Overall passed: `False`

| Stage | Status | Failed Criteria |
|---|---:|---|
| Limited Core Grid Test | error | summary.total_combinations_tested actual=None expected={'valid_parameter_combination_count': '1 fixed combo or 8-120 tunable combos'}<br>summary.percentage_profitable_iterations actual=None expected={'min': 0.7}<br>strategy.entry.params.timeframe_minutes (15) must match variant timeframe (1 minutes). |
| Limited Monkey Test | skipped | prior stage failed |
| Walk Forward Analysis (WFA) | skipped | prior stage failed |
| WFA OOS Monkey Test | skipped | prior stage failed |
| WFA OOS Monte Carlo | skipped | prior stage failed |
| Simulated Incubation (OOS) Core | skipped | prior stage failed |
| Simulated Incubation (OOS) Monkey | skipped | prior stage failed |
| Acceptance OOS Test | skipped | prior stage failed |

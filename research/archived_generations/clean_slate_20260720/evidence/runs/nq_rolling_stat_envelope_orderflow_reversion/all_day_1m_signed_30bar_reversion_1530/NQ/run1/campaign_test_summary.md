# Campaign Test Summary

- Campaign: `nq_rolling_stat_envelope_orderflow_reversion`
- Variant: `all_day_1m_signed_30bar_reversion_1530`
- Timeframe: `1m`
- Overall passed: `False`

| Stage | Status | Failed Criteria |
|---|---:|---|
| Limited Core Grid Test | failed | summary.percentage_profitable_iterations actual=0.0 expected={'min': 0.7} |
| Limited Monkey Test | skipped | prior stage failed |
| Walk Forward Analysis (WFA) | skipped | prior stage failed |
| WFA OOS Monkey Test | skipped | prior stage failed |
| WFA OOS Monte Carlo | skipped | prior stage failed |
| Simulated Incubation (OOS) Core | skipped | prior stage failed |
| Simulated Incubation (OOS) Monkey | skipped | prior stage failed |
| Acceptance OOS Test | skipped | prior stage failed |

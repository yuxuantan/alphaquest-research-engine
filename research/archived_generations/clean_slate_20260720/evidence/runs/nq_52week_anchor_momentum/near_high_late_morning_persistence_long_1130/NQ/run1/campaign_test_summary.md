# Campaign Test Summary

- Campaign: `nq_52week_anchor_momentum`
- Variant: `near_high_late_morning_persistence_long_1130`
- Timeframe: `5m`
- Overall passed: `False`

| Stage | Status | Failed Criteria |
|---|---:|---|
| Limited Core Grid Test | error | summary.total_combinations_tested actual=None expected={'valid_parameter_combination_count': '1 fixed combo or 8-120 tunable combos'}<br>summary.percentage_profitable_iterations actual=None expected={'min': 0.7}<br>Unsupported data.feature_set: completed_intraday_bars_plus_internal_prior_252_session_anchor. Expected one of ['full', 'intraday_capitulation_mr', 'none', 'opening_range', 'pdh_pdl_sweep']. |
| Limited Monkey Test | skipped | prior stage failed |
| Walk Forward Analysis (WFA) | skipped | prior stage failed |
| WFA OOS Monkey Test | skipped | prior stage failed |
| WFA OOS Monte Carlo | skipped | prior stage failed |
| Simulated Incubation (OOS) Core | skipped | prior stage failed |
| Simulated Incubation (OOS) Monkey | skipped | prior stage failed |
| Acceptance OOS Test | skipped | prior stage failed |

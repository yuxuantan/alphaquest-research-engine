# Campaign Test Summary

- Campaign: `calendar_session_seasonality`
- Variant: `midweek_morning_strength_macro_event_day`
- Timeframe: `15m`
- Overall passed: `False`

| Stage | Status | Failed Criteria |
|---|---:|---|
| Limited Core Grid Test | passed |  |
| Limited Monkey Test | failed | summary.core_beats_monkey_net_profit_rate actual=0.834375 expected={'min': 0.9}<br>summary.core_beats_monkey_max_drawdown_rate actual=0.825 expected={'min': 0.9} |
| Walk Forward Analysis (WFA) | skipped | prior stage failed |
| WFA OOS Monkey Test | skipped | prior stage failed |
| WFA OOS Monte Carlo | skipped | prior stage failed |
| Simulated Incubation (OOS) Core | skipped | prior stage failed |
| Simulated Incubation (OOS) Monkey | skipped | prior stage failed |

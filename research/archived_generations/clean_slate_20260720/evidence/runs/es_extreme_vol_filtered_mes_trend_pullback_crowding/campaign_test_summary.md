# Campaign Test Summary: es_extreme_vol_filtered_mes_trend_pullback_crowding

Verdict: FAIL

All original and rescue runs failed. Best-stage variants reached WFA OOS Monte Carlo but failed simulated_incubation_core; no run reached acceptance OOS or candidate reporting.

| variant_id | run | terminal stage | terminal net | PF | MAR | trades | failed criteria |
|---|---|---|---:|---:|---:|---:|---|
| exclude_extreme_range10_trade_morning_1030 | rescue1 | simulated_incubation_core | -96.25 | 0.996 | -0.017 | 68 | metrics.profit_factor;metrics.mar |
| exclude_extreme_absret5_trade_morning_1030 | run1 | simulated_incubation_core | -13517.50 | 0.657 | -0.786 | 81 | metrics.profit_factor;metrics.mar |
| exclude_extreme_downside20_trade_morning_1030 | run1 | simulated_incubation_core | -13517.50 | 0.657 | -0.786 | 81 | metrics.profit_factor;metrics.mar |
| exclude_extreme_range10_trade_morning_1030 | run1 | simulated_incubation_core | -13517.50 | 0.657 | -0.786 | 81 | metrics.profit_factor;metrics.mar |
| exclude_extreme_absret5_trade_morning_1030 | rescue1 | limited_monkey_test | 8052.50 |  |  | 57 | summary.core_beats_monkey_max_drawdown_rate |
| exclude_extreme_vol20_trade_morning_1030 | run1 | limited_monkey_test | 7835.00 |  |  | 43 | summary.core_beats_monkey_max_drawdown_rate |
| exclude_extreme_downside20_trade_morning_1030 | rescue1 | limited_monkey_test | 7710.00 |  |  | 43 | summary.core_beats_monkey_max_drawdown_rate |
| vol_downshift_trade_morning_1030 | run1 | limited_monkey_test | 6828.75 |  |  | 63 | summary.core_beats_monkey_max_drawdown_rate |
| exclude_extreme_vol20_trade_morning_1030 | rescue1 | limited_monkey_test | 5365.00 |  |  | 52 | summary.core_beats_monkey_net_profit_rate;summary.core_beats_monkey_max_drawdown_rate |

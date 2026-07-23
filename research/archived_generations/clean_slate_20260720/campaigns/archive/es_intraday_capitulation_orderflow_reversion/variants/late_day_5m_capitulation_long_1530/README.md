# late_day_5m_capitulation_long_1530

Campaign: `es_intraday_capitulation_orderflow_reversion`

This variant trades long after a completed 5-minute downside capitulation bar from 11:00 to 15:30 ET, avoiding the opening auction and focusing on later liquidity shocks. Entry is next bar open after the completed signal bar, with a stop beyond the capitulation low, fixed-R target, and same-day flatten.

Modules: `intraday_capitulation_mr`, `sweep_extreme`, `fixed_r`.

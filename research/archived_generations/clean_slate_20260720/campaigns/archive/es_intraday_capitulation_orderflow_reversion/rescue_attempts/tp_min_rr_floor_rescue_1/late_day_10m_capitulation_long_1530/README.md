# late_day_10m_capitulation_long_1530

Campaign: `es_intraday_capitulation_orderflow_reversion`

This variant trades long after a completed 10-minute downside capitulation bar from 11:00 to 15:30 ET. It tests whether later-session selling pressure over a broader completed window mean-reverts after liquidity demand is absorbed. Entry is next bar open, with a stop beyond the capitulation low, fixed-R target, and same-day flatten.

Modules: `intraday_capitulation_mr`, `sweep_extreme`, `fixed_r`.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_intraday_capitulation_orderflow_reversion/late_day_10m_capitulation_long_1530/run1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.

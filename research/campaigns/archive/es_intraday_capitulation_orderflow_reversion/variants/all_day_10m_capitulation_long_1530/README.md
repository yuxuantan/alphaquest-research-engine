# all_day_10m_capitulation_long_1530

Campaign: `es_intraday_capitulation_orderflow_reversion`

This variant trades long after a completed 10-minute downside capitulation bar from 09:30 to 15:30 ET. The longer bar asks whether exhaustion requires a broader completed pressure window than the 5-minute variants. Entry is next bar open, with a stop beyond the capitulation low, fixed-R target, and same-day flatten.

Modules: `intraday_capitulation_mr`, `sweep_extreme`, `fixed_r`.

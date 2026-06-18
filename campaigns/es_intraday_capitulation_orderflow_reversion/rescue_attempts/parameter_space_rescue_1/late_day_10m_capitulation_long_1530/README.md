# late_day_10m_capitulation_long_1530

Campaign: `es_intraday_capitulation_orderflow_reversion`

This variant trades long after a completed 10-minute downside capitulation bar from 11:00 to 15:30 ET. It tests whether later-session selling pressure over a broader completed window mean-reverts after liquidity demand is absorbed. Entry is next bar open, with a stop beyond the capitulation low, fixed-R target, and same-day flatten.

Modules: `intraday_capitulation_mr`, `sweep_extreme`, `fixed_r`.


Rescue 1: parameter-space-only rescue with stricter RSI/sell-imbalance thresholds, wider capitulation-low stop offsets, and smaller fixed-R targets. No module, data, timeframe, or edge mechanic changed.

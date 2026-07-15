# all_day_5m_capitulation_long_1530

Campaign: `es_intraday_capitulation_orderflow_reversion`

This variant trades long after a completed 5-minute downside capitulation bar from 09:30 to 15:30 ET. The signal requires close near the low, close below completed VWAP, session-local oversold RSI, elevated volume, and completed-window aggregate sell imbalance. Entry is next bar open, with a stop beyond the capitulation low, fixed-R target, and same-day flatten.

Modules: `intraday_capitulation_mr`, `sweep_extreme`, `fixed_r`.

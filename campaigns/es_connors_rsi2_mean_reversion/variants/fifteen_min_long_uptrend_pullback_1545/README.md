# fifteen_min_long_uptrend_pullback_1545

Mechanic: on completed 15-minute RTH bars, go long ES when RSI2 is oversold while price remains above the configured moving-average trend filter.

Entry timing: signals use the completed bar close and enter on the next 15-minute bar open.

Stop logic: `percent_from_entry`, tuned only through `sl.params.stop_pct`.

Take-profit / exit logic: `fixed_r`, tuned only through `tp.params.target_r_multiple`; otherwise flatten at 15:45 ET.

Session restrictions: RTH only, America/New_York timestamps, one trade per day, no overnight exposure.

Lookahead control: RSI2 and moving average are computed only from completed bars.

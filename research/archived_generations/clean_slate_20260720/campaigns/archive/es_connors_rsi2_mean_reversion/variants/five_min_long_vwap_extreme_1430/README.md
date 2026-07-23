# five_min_long_vwap_extreme_1430

Mechanic: on completed 5-minute RTH bars, go long ES when RSI2 is oversold, price is above the moving-average trend filter, and price is stretched below running VWAP by the configured tick extension.

Entry timing: signals use the completed bar close and enter on the next 5-minute bar open.

Stop logic: `percent_from_entry`, tuned only through `sl.params.stop_pct`.

Take-profit / exit logic: `fixed_r`, tuned only through `tp.params.target_r_multiple`; otherwise flatten at 15:55 ET.

Session restrictions: RTH only, America/New_York timestamps, one trade per day, no overnight exposure.

Lookahead control: RSI2, moving average, and VWAP are computed only from completed bars.

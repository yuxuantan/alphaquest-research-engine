# thirty_min_two_sided_trend_reversion_1530

Mechanic: on completed 30-minute RTH bars, go long ES after RSI2 oversold pullbacks in an uptrend or short ES after RSI2 overbought bounces in a downtrend.

Entry timing: signals use the completed bar close and enter on the next 30-minute bar open.

Stop logic: `percent_from_entry`, tuned only through `sl.params.stop_pct`.

Take-profit / exit logic: `fixed_r`, tuned only through `tp.params.target_r_multiple`; otherwise flatten at 15:30 ET.

Session restrictions: RTH only, America/New_York timestamps, one trade per day, no overnight exposure.

Lookahead control: RSI2 and moving average are computed only from completed bars.

# round_number_downside_breakout_short

Mechanic: From 09:45 through 13:30 ET, enter short when a completed 5-minute bar crosses from above to below a nearby ES round-number barrier; flatten by 15:55 ET unless stop or target is hit.

The signal uses only the completed 5-minute OHLC bar and fixed ES price barriers at the configured round-number interval. Entry occurs no earlier than the next bar open.

Stop module: `percent_from_entry`. Target module: `fixed_r`. No overnight exposure is allowed.

# morning_round_support_reclaim_long

Mechanic: From 09:35 through 11:30 ET, enter long after a completed 5-minute bar trades through and closes back above a nearby ES round-number barrier; flatten by 15:55 ET unless stop or target is hit.

The signal uses only the completed 5-minute OHLC bar and fixed ES price barriers at the configured round-number interval. Entry occurs no earlier than the next bar open.

Stop module: `percent_from_entry`. Target module: `fixed_r`. No overnight exposure is allowed.

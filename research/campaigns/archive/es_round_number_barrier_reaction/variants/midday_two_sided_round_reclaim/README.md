# midday_two_sided_round_reclaim

Mechanic: From 11:30 through 14:30 ET, trade the first completed 5-minute two-sided reclaim/rejection of a nearby ES round-number barrier; flatten by 15:55 ET unless stop or target is hit.

The signal uses only the completed 5-minute OHLC bar and fixed ES price barriers at the configured round-number interval. Entry occurs no earlier than the next bar open.

Stop module: `percent_from_entry`. Target module: `fixed_r`. No overnight exposure is allowed.

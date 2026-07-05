# late_morning_20_80_two_sided_reclaim_pivot

Mechanic: From 10:00 through 12:30 ET, trade the first completed NQ 5-minute reclaim or rejection around a terminal 20/80 level only when completed 5/15-minute pivot structure agrees with the signal direction.

The signal uses only completed 5-minute bars, fixed modulo-100 NQ 20/80 price endings, and completed pivot structure. Entry occurs no earlier than the next bar open.

Stop module: `fixed_dollar_per_contract`. Target module: `fixed_r`. No overnight exposure is allowed.

# morning_20_80_upside_breakout_pivot_long

Mechanic: From 09:45 through 12:30 ET, enter long when a completed NQ 5-minute bar crosses from below to above a terminal 20/80 level, with completed 5/15-minute pivot structure agreeing long.

The signal uses only completed 5-minute bars, fixed modulo-100 NQ 20/80 price endings, and completed pivot structure. Entry occurs no earlier than the next bar open.

Stop module: `fixed_dollar_per_contract`. Target module: `fixed_r`. No overnight exposure is allowed.

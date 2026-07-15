# morning_20_80_downside_breakout_pivot_short

Mechanic: From 09:45 through 12:30 ET, enter short when a completed NQ 5-minute bar crosses from above to below a terminal 20/80 level, with completed 5/15-minute pivot structure agreeing short.

The signal uses only completed 5-minute bars, fixed modulo-100 NQ 20/80 price endings, and completed pivot structure. Entry occurs no earlier than the next bar open.

Stop module: `fixed_dollar_per_contract`. Target module: `fixed_r`. No overnight exposure is allowed.

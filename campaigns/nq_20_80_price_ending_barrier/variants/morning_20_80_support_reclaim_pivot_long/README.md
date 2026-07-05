# morning_20_80_support_reclaim_pivot_long

Mechanic: From 09:35 through 11:30 ET, enter long after a completed NQ 5-minute bar probes a terminal 20/80 level and closes back above it, with completed 5/15-minute pivot structure agreeing long.

The signal uses only completed 5-minute bars, fixed modulo-100 NQ 20/80 price endings, and completed pivot structure. Entry occurs no earlier than the next bar open.

Stop module: `fixed_dollar_per_contract`. Target module: `fixed_r`. No overnight exposure is allowed.

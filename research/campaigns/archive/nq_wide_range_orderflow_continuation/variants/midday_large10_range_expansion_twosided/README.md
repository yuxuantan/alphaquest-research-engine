# midday_large10_range_expansion_twosided

From 11:00 through 14:00 ET, trade in the direction of a completed wide-range 5-minute bar that closes near the relevant extreme and has aligned large-10 signed-volume imbalance.

Mechanics review: the price-action range expansion must occur first, and completed aggregate orderflow only confirms participation on that same completed bar. Signals use the 5-minute bar close and can enter no earlier than the next bar open.

Parameter grid: `min_range_ticks` x `min_orderflow_imbalance` x `stop_pct` x `target_r_multiple` = 54 combinations. No PnL was inspected before this grid was written.

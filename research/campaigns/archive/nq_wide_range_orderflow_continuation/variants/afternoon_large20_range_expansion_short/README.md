# afternoon_large20_range_expansion_short

From 13:00 through 15:15 ET, enter short only after a completed wide-range 5-minute bar closes near its low and has aligned large-20 signed-volume imbalance.

Mechanics review: the price-action range expansion must occur first, and completed aggregate orderflow only confirms participation on that same completed bar. Signals use the 5-minute bar close and can enter no earlier than the next bar open.

Parameter grid: `min_range_ticks` x `min_orderflow_imbalance` x `stop_pct` x `target_r_multiple` = 54 combinations. No PnL was inspected before this grid was written.

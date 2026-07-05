# morning_signed_range_expansion_short

From 09:35 through 11:30 ET, enter short only after a completed 5-minute NQ bar has a wide range, a negative body, closes near its low, has at least normal relative volume, and has same-direction completed signed-volume imbalance.

Mechanics review: the price-action range expansion must occur first, and completed aggregate orderflow only confirms participation on that same completed bar. Signals use the 5-minute bar close and can enter no earlier than the next bar open.

Parameter grid: `min_range_ticks` x `min_orderflow_imbalance` x `stop_pct` x `target_r_multiple` = 54 combinations. No PnL was inspected before this grid was written.

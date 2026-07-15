# midday_large10_range_expansion_twosided

From 11:00 through 14:00 ET, trade in the direction of a completed wide-range 5-minute bar that closes near the relevant extreme and has aligned large-10 signed-volume imbalance.

Mechanics review: the price-action range expansion must occur first, and completed aggregate orderflow only confirms participation on that same completed bar. Signals use the 5-minute bar close and can enter no earlier than the next bar open.

Parameter grid: `min_range_ticks` x `min_orderflow_imbalance` x `stop_pct` x `target_r_multiple` = 81 combinations. No PnL was inspected before this grid was written.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_wide_range_orderflow_continuation/midday_large10_range_expansion_twosided/run1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.

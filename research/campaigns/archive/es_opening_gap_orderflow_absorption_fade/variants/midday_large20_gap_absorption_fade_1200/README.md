# midday_large20_gap_absorption_fade_1200

Campaign: `es_opening_gap_orderflow_absorption_fade`

Mechanic: after a 1-3 point ES RTH opening gap from the prior RTH close, wait for the completed 11:30-12:00 ET window. Fade the gap only when large-20 aggregate signed-flow imbalance is against the gap.

Why this expresses the edge: this version tests slower inventory absorption after the opening auction has matured, while still leaving enough session time before forced flatten.

Entry module: `opening_gap_orderflow_fade`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

Parameter grid: `entry.params.min_opening_gap_ticks` x `entry.params.min_orderflow_imbalance` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 81 combinations.

Lookahead controls: prior RTH close is completed before the session, the flow window uses only completed bars, and the engine enters no earlier than the next bar open.

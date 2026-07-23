# late_morning_large10_gap_absorption_fade_1100

Campaign: `es_opening_gap_orderflow_absorption_fade`

Mechanic: after a 1-3 point ES RTH opening gap from the prior RTH close, wait for the completed 10:45-11:00 ET window. Fade the gap only when large-10 aggregate signed-flow imbalance is against the gap.

Why this expresses the edge: large-10 flow is a broader aggregate-trade proxy than large-20, testing whether absorption is visible before only the largest trade-size bucket is isolated.

Entry module: `opening_gap_orderflow_fade`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

Parameter grid: `entry.params.min_opening_gap_ticks` x `entry.params.min_orderflow_imbalance` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 81 combinations.

Lookahead controls: prior RTH close is completed before the session, the flow window uses only completed bars, and the engine enters no earlier than the next bar open.

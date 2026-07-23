# late_morning_large20_gap_absorption_fade_1100

Campaign: `es_opening_gap_orderflow_absorption_fade`

Mechanic: after a 1-3 point ES RTH opening gap from the prior RTH close, wait for the completed 10:45-11:00 ET window. Fade the gap only when large-20 aggregate signed-flow imbalance is against the gap.

Why this expresses the edge: this variant tests whether absorption is most visible after the first hour has digested the gap but before the lunch regime.

Entry module: `opening_gap_orderflow_fade`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

Parameter grid: `entry.params.min_opening_gap_ticks` x `entry.params.min_orderflow_imbalance` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 81 combinations.

Lookahead controls: prior RTH close is completed before the session, the flow window uses only completed bars, and the engine enters no earlier than the next bar open.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_opening_gap_orderflow_absorption_fade/late_morning_large20_gap_absorption_fade_1100/run1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.

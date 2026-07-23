# morning_down_open_reclaim_long

Campaign: `es_session_open_orderflow_reclaim`

Mechanic: After ES has traded at least the configured distance below the current RTH open on a prior completed bar, buy a completed reclaim of the RTH open when same-bar aggregate signed flow is positive enough.

Why this expresses the edge: the current RTH open is the auction-anchor level, the excursion must already be visible on a prior completed bar, and the signal bar must close back through the open with `large10` orderflow aligned with the trade direction.

Entry module: `session_open_orderflow_reclaim`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

Parameter grid: `entry.params.min_open_extension_ticks` x `entry.params.min_orderflow_imbalance` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 81 combinations.

Lookahead controls: the RTH open is known at the current session open, the away-from-open excursion is required on a prior completed bar, the reclaim/rejection uses the completed signal bar, and the engine enters no earlier than the next bar open.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_session_open_orderflow_reclaim/morning_down_open_reclaim_long/run1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.

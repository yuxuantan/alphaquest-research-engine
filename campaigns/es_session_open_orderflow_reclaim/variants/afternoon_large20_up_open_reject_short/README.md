# afternoon_large20_up_open_reject_short

Campaign: `es_session_open_orderflow_reclaim`

Mechanic: In the afternoon, sell only after a prior completed upside excursion above the current RTH open and a completed rejection back through the open confirmed by large-20 selling pressure.

Why this expresses the edge: the current RTH open is the auction-anchor level, the excursion must already be visible on a prior completed bar, and the signal bar must close back through the open with `large20` orderflow aligned with the trade direction.

Entry module: `session_open_orderflow_reclaim`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

Parameter grid: `entry.params.min_open_extension_ticks` x `entry.params.min_orderflow_imbalance` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 81 combinations.

Lookahead controls: the RTH open is known at the current session open, the away-from-open excursion is required on a prior completed bar, the reclaim/rejection uses the completed signal bar, and the engine enters no earlier than the next bar open.

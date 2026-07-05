# midday_large10_two_sided_open_reclaim

Campaign: `nq_session_open_orderflow_reclaim`

Mechanic: From late morning through early afternoon, trade either side of the current RTH open only after a prior completed excursion and a completed reclaim/rejection confirmed by large-10 aggregate flow.

Why this expresses the edge: the current RTH open is the auction-anchor level, the excursion must already be visible on a prior completed bar, and the signal bar must close back through the open with `large10` orderflow aligned with the trade direction.

Entry module: `session_open_orderflow_reclaim`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

Parameter grid: `entry.params.min_open_extension_ticks` x `entry.params.min_orderflow_imbalance` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 27 combinations.

Lookahead controls: the RTH open is known at the current session open, the away-from-open excursion is required on a prior completed bar, the reclaim/rejection uses the completed signal bar, and the engine enters no earlier than the next bar open.

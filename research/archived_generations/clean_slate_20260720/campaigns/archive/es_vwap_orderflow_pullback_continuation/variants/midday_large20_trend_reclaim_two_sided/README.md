# midday_large20_trend_reclaim_two_sided

Campaign: `es_vwap_orderflow_pullback_continuation`

Mechanic: from 11:00 to 14:30 ET, trade a two-sided VWAP trend-reclaim setup only when the completed 5-minute reclaim bar has large-20 signed-flow imbalance aligned with the trade direction.

Why this expresses the edge: the midday window tests a later institutional-value reclaim; large-20 flow is the stricter orderflow confirmation for larger aggressive participation.

Entry module: `vwap_orderflow_pullback_continuation`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

Parameter grid: `entry.params.required_trend_closes` x `entry.params.min_orderflow_imbalance` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 81 combinations.

Lookahead controls: VWAP, trend count, pullback, reclaim, and large-20 confirmation use completed 5-minute bars only; the engine enters no earlier than the next bar open.

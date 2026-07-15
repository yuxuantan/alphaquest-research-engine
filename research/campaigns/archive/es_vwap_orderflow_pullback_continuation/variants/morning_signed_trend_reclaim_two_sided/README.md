# morning_signed_trend_reclaim_two_sided

Campaign: `es_vwap_orderflow_pullback_continuation`

Mechanic: from 09:45 to 12:00 ET, trade a two-sided VWAP trend-reclaim setup only when the completed 5-minute reclaim bar has signed-volume imbalance aligned with the trade direction.

Why this expresses the edge: VWAP defines the intraday value reference and price-action trend context; aggregate signed flow confirms that the reclaim has aggressive participation rather than just a passive bounce.

Entry module: `vwap_orderflow_pullback_continuation`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

Parameter grid: `entry.params.required_trend_closes` x `entry.params.min_orderflow_imbalance` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 81 combinations.

Lookahead controls: VWAP, trend count, pullback, reclaim, and signed-volume confirmation use completed 5-minute bars only; the engine enters no earlier than the next bar open.

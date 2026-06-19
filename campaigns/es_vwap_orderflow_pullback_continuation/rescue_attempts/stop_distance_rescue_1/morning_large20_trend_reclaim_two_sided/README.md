# morning_large20_trend_reclaim_two_sided

Campaign: `es_vwap_orderflow_pullback_continuation`

Mechanic: from 09:45 to 12:00 ET, trade a two-sided VWAP trend-reclaim setup only when the completed 5-minute reclaim bar has large-20 signed-flow imbalance aligned with the trade direction.

Why this expresses the edge: VWAP defines the price-action value reference; large-20 aggregate flow is a stricter participation filter intended to reject weak reclaims without larger trade-size confirmation.

Entry module: `vwap_orderflow_pullback_continuation`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

Parameter grid: `entry.params.required_trend_closes` x `entry.params.min_orderflow_imbalance` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 81 combinations.

Lookahead controls: VWAP, trend count, pullback, reclaim, and large-20 confirmation use completed 5-minute bars only; the engine enters no earlier than the next bar open.


## stop_distance_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_vwap_orderflow_pullback_continuation/morning_large20_trend_reclaim_two_sided/run1`. Only stop distance was widened by 1.5x; entry, target/exit, data, costs, fills, sessions, and validation gates are unchanged.

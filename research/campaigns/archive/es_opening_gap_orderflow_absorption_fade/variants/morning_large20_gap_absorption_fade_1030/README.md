# morning_large20_gap_absorption_fade_1030

Campaign: `es_opening_gap_orderflow_absorption_fade`

Mechanic: after a 1-3 point ES RTH opening gap from the prior RTH close, wait for the completed 10:00-10:30 ET window. Fade the gap only when large-20 aggregate signed-flow imbalance is against the gap.

Why this expresses the edge: this gives the market more time to absorb the opening gap and asks whether later large-trade pressure against the gap predicts intraday mean reversion.

Entry module: `opening_gap_orderflow_fade`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

Parameter grid: `entry.params.min_opening_gap_ticks` x `entry.params.min_orderflow_imbalance` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 81 combinations.

Lookahead controls: prior RTH close is completed before the session, the flow window uses only completed bars, and the engine enters no earlier than the next bar open.

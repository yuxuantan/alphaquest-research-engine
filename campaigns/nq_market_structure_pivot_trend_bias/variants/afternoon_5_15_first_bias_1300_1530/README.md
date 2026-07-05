# afternoon_5_15_first_bias_1300_1530

Between 13:00:00 and 15:30:00 ET, trade the first completed-bar NQ signal where 5/15-minute confirmed swing-pivot states align. Long requires HH/HL; short requires LH/LL; no trade is allowed if structure is mixed, insufficient, or opposite.

Why this should be profitable before testing: confirmed multi-timeframe pivot agreement is a direct local trend definition. Acting on the first confirmed bias inside a fixed window should avoid arbitrary clock sampling while preserving enough same-day NQ opportunity to test under costs.

Time/session rationale: the 13:00:00-15:30:00 ET window is fixed before PnL testing and uses completed bars only; all positions flatten at 15:55 ET.

Parameter grid declared before testing: `entry.params.min_pivot_move_ticks` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 27 combinations. `target_r_multiple` is never below 1.0R.

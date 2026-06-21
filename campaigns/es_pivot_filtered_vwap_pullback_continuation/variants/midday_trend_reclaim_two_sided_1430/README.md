# midday_trend_reclaim_two_sided_1430

From 10:30 to 14:30 ET, require a completed VWAP-side trend and a pullback/reclaim sequence back in the trend direction. Accept only when carried 5/15-minute completed pivot structure supports the continuation and no checked timeframe opposes it.

Why this should be profitable before testing: VWAP is an institutional benchmark and the base signal requires a completed pullback and reclaim/rejection back to the trend side. The fixed carried 5/15-minute pivot filter allows trades only when completed structure supports the continuation direction and neither checked timeframe opposes it.

Parameter grid declared before testing: 54 combinations. Entry parameters are under `entry.params.base_params.*`; pivot timeframes, carry behavior, and alignment rule are fixed and not tunable. `target_r_multiple` is never below 1.0R.

# failed_vwap_break_two_sided_1500

From 09:45 to 15:00 ET, require an established VWAP-side trend, a completed false break through VWAP against that trend, and a reclaim back to the trend side. Accept only when carried 5/15-minute pivot structure supports the reclaim direction and no checked timeframe opposes it.

Why this should be profitable before testing: VWAP is an institutional benchmark and the base signal requires a completed pullback and reclaim/rejection back to the trend side. The fixed carried 5/15-minute pivot filter allows trades only when completed structure supports the continuation direction and neither checked timeframe opposes it.

Parameter grid declared before testing: 54 combinations. Entry parameters are under `entry.params.base_params.*`; pivot timeframes, carry behavior, and alignment rule are fixed and not tunable. `target_r_multiple` is never below 1.0R.

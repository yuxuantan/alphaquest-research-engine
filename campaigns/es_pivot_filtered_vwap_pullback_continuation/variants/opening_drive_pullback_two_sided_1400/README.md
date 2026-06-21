# opening_drive_pullback_two_sided_1400

After a completed directional opening drive, wait until 14:00 ET for the first pullback to VWAP and reclaim/rejection back in the drive direction. Accept only when carried 5/15-minute pivot structure supports the same direction and no checked timeframe opposes it.

Why this should be profitable before testing: VWAP is an institutional benchmark and the base signal requires a completed pullback and reclaim/rejection back to the trend side. The fixed carried 5/15-minute pivot filter allows trades only when completed structure supports the continuation direction and neither checked timeframe opposes it.

Parameter grid declared before testing: 54 combinations. Entry parameters are under `entry.params.base_params.*`; pivot timeframes, carry behavior, and alignment rule are fixed and not tunable. `target_r_multiple` is never below 1.0R.

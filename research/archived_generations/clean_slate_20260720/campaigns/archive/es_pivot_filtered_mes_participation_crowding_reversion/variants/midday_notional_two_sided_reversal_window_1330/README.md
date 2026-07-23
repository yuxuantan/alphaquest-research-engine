# midday_notional_two_sided_reversal_window_1330

From 11:00 through 13:30 ET, use completed 1-minute bars to find the first high-MES-notional-share 30-minute ES move. Fade only in the direction supported by carried 5/15-minute completed pivot structure. Enter next bar and flatten by 14:30.

Why this should be profitable before testing: the base MES participation trigger identifies possible smaller-contract crowding, and the fixed carried completed-pivot filter only allows the fade when the reversal direction agrees with current market structure.

Parameter grid declared before testing: `entry.params.base_params.share_rank_min` x `entry.params.base_params.min_abs_return_ticks` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 81 combinations. Pivot timeframes, carry behavior, and alignment count are fixed, not tunable. `target_r_multiple` is never below 1.0R.

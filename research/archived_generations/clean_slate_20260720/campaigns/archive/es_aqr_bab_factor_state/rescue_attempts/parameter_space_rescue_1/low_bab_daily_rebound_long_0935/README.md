# low_bab_daily_rebound_long_0935 rescue1

Rescue attempt 1 preserves the original AQR BAB factor-state mechanic, entry module, rank/value columns, setup mode, direction, entry time, data window, costs, fill assumptions, session rules, and validation gates.

Allowed rescue changes: only `entry.params.bab_rank_threshold`, `sl.params.stop_pct`, and `tp.params.target_r_multiple` parameter spaces are changed.

Stop module: `percent_from_entry`. Target module: `fixed_r`. No overnight exposure is allowed.

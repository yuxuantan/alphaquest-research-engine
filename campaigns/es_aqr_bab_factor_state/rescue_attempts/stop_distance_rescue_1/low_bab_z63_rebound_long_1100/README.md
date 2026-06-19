# low_bab_z63_rebound_long_1100 rescue1

Rescue attempt 1 preserves the original AQR BAB factor-state mechanic, entry module, rank/value columns, setup mode, direction, entry time, data window, costs, fill assumptions, session rules, and validation gates.

Allowed rescue changes: only `entry.params.bab_rank_threshold`, `sl.params.stop_pct`, and `tp.params.target_r_multiple` parameter spaces are changed.

Stop module: `percent_from_entry`. Target module: `fixed_r`. No overnight exposure is allowed.


## stop_distance_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_aqr_bab_factor_state/low_bab_z63_rebound_long_1100/rescue1`. Only stop distance was widened by 1.5x; entry, target/exit, data, costs, fills, sessions, and validation gates are unchanged.

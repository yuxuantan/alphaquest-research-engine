# morning_signed_vah_acceptance_long rescue1

Rescue attempt 1 keeps the original prior value-area acceptance mechanic. Original top rows were positive but not grid-robust; rescue keeps prior-VAH acceptance and tests adjacent continuation-oriented target values with the same stop neighborhood.

Allowed changes only: `entry.params.breakout_buffer_ticks`, `entry.params.min_orderflow_imbalance`, `sl.params.stop_pct`, and `tp.params.target_r_multiple` parameter spaces.


## stop_distance_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_prior_value_area_orderflow_acceptance/morning_signed_vah_acceptance_long/rescue1`. Only stop distance was widened by 1.5x; entry, target/exit, data, costs, fills, sessions, and validation gates are unchanged.

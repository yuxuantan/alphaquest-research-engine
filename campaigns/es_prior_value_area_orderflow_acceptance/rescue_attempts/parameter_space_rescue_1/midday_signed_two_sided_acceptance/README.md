# midday_signed_two_sided_acceptance rescue1

Rescue attempt 1 keeps the original prior value-area acceptance mechanic. Original midday acceptance was weak; rescue keeps the same mechanic and tests whether wider stops with shorter fixed-R exits better handle midday re-entry noise without changing filters.

Allowed changes only: `entry.params.breakout_buffer_ticks`, `entry.params.min_orderflow_imbalance`, `sl.params.stop_pct`, and `tp.params.target_r_multiple` parameter spaces.

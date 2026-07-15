# morning_signed_val_acceptance_short rescue1

Rescue attempt 1 keeps the original prior value-area acceptance mechanic. Original short side was negative; rescue keeps prior-VAL acceptance and tests whether slightly wider invalidation plus conservative targets better matches downside acceptance noise.

Allowed changes only: `entry.params.breakout_buffer_ticks`, `entry.params.min_orderflow_imbalance`, `sl.params.stop_pct`, and `tp.params.target_r_multiple` parameter spaces.

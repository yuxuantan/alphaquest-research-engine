# first30_signed_flow_long_only_1530

Campaign: `nq_gao_last_half_hour_orderflow_confirmation`

Entry module: `gao_last_half_hour_orderflow`. Stop module: `percent_from_entry`. Target module: `fixed_r`.

Mechanic: Long-only 15:30 ET continuation after a completed positive first-30-minute NQ return with positive signed-volume imbalance.

Parameter grid: `entry.params.min_first_return_ticks` x `entry.params.min_orderflow_imbalance` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 81 combinations.

Pre-PnL density note: Worst declared entry corner before PnL is about 11.4 signals/year; broad long-only corners are above 50/year.

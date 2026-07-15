# first30_broad_large_alignment_1530

Campaign: `nq_gao_last_half_hour_orderflow_confirmation`

Entry module: `gao_last_half_hour_orderflow`. Stop module: `percent_from_entry`. Target module: `fixed_r`.

Mechanic: Two-sided 15:30 ET continuation from completed first-30-minute return requiring both signed-volume and large20 imbalance alignment.

Parameter grid: `entry.params.min_first_return_ticks` x `entry.params.min_orderflow_imbalance` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 81 combinations.

Pre-PnL density note: Worst declared entry corner before PnL is about 14.6 signals/year; broad and middle corners retain usable density.

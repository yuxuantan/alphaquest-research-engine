# first30_large20_flow_two_sided_1530

Campaign: `nq_gao_last_half_hour_orderflow_confirmation`

Entry module: `gao_last_half_hour_orderflow`. Stop module: `percent_from_entry`. Target module: `fixed_r`.

Mechanic: Two-sided 15:30 ET continuation from completed first-30-minute price return plus same-direction large20 signed-volume imbalance.

Parameter grid: `entry.params.min_first_return_ticks` x `entry.params.min_orderflow_imbalance` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 81 combinations.

Pre-PnL density note: Worst declared entry corner before PnL is about 44.6 signals/year and most neighboring corners are above 50/year.

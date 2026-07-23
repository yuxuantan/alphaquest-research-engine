# first60_signed_flow_two_sided_1530

Campaign: `es_gao_last_half_hour_orderflow_confirmation`

Mechanic: First 60-minute price return and total signed-flow imbalance point the same way; enter for last-half-hour continuation.

Entry module: `gao_last_half_hour_orderflow`. Stop module: `percent_from_entry`. Target module: `fixed_r`.

Parameter grid: `entry.params.min_first_return_ticks` x `entry.params.min_orderflow_imbalance` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 36 combinations.

Lookahead controls: first-window price and aggregate orderflow are completed before the 15:30 ET signal; the engine enters no earlier than the next bar open and flattens at 15:55 ET.

# late_morning30_signed_two_sided_1130

Campaign: `es_mes_lead_lag_catchup`.

Mechanic: from 11:00 through 12:30 ET, follow the completed rolling 30-minute MES direction in ES only when ES lags MES by the configured tick gap and MES signed-flow imbalance confirms the MES direction.

Entry module: `es_mes_lead_lag`.
Stop module: `sweep_extreme`.
Target module: `fixed_r`.

Parameter grid: `entry.params.min_mes_return_ticks` x `entry.params.min_lag_gap_ticks` x `sl.params.stop_offset_ticks` x `tp.params.target_r_multiple` = 81 combinations.

Lookahead controls: all return and orderflow features end at the signal bar close; the engine enters no earlier than the next ES bar open.


## stop_distance_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_mes_lead_lag_catchup/late_morning30_signed_two_sided_1130/run1`. Only stop distance was widened by 1.5x; entry, target/exit, data, costs, fills, sessions, and validation gates are unchanged.

# afternoon60_mes_signed_1400

Campaign: `es_mes_aligned_flow_continuation`.

Mechanic: at the completed 14:00 ET signal, trade ES in the direction of the completed 60-minute ES move only when completed 60-minute MES signed-flow imbalance confirms that direction.

Entry module: `es_mes_aligned_flow_continuation`.
Stop module: `sweep_extreme`.
Target module: `fixed_r`.

Parameter grid: `entry.params.min_es_return_ticks` x `entry.params.min_mes_flow_imbalance` x `sl.params.stop_offset_ticks` x `tp.params.target_r_multiple` = 81 combinations.

Lookahead controls: all features end at the signal bar close and the engine enters no earlier than the next bar open.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_mes_aligned_flow_continuation/afternoon60_mes_signed_1400/run1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.

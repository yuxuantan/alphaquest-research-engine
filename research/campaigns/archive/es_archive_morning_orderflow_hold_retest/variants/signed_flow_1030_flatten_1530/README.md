# es_archive_morning_orderflow_hold_retest / signed_flow_1030_flatten_1530

At the completed 10:30 ET first-hour close, trade ES in the direction of the 09:30-10:30 return only when completed signed_imbalance confirms that direction, then hold until 15:30:00 unless stop or target is hit.

Parameter grid: 81 combinations, capped to at most two entry parameters, one stop parameter, and one target parameter before testing.

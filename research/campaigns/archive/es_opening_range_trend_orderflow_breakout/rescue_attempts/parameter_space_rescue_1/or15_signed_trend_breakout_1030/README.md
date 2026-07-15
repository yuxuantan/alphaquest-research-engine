# or15_signed_trend_breakout_1030 Rescue 1

Campaign: `es_opening_range_trend_orderflow_breakout`

This is the single allowed rescue for `or15_signed_trend_breakout_1030`. It keeps the same `opening_range_trend_orderflow_breakout` entry module, `opening_range_edge` stop module, `fixed_r` target module, timeframe, data, costs, fills, sessions, prop rules, and validation gates.

Changes: stricter `entry.params.min_orderflow_imbalance`, wider `sl.params.stop_offset_ticks`, and larger `tp.params.target_r_multiple`.

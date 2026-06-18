# morning_15_30_large20_trend_flow_1030

Campaign: `es_trend_aligned_orderflow_continuation`

Mechanic: at the completed 10:30 ET bar, trade long only if 15-minute and 30-minute completed price structure both show HH/HL and large-20 signed-flow imbalance is positive; trade short only if both horizons show LH/LL and large-20 signed-flow imbalance is negative.

Entry module: `trend_aligned_orderflow_continuation`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

Parameter grid: `entry.params.min_orderflow_imbalance` x `entry.params.min_trend_move_ticks` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 36 combinations.

Lookahead controls: trend windows and aggregate orderflow use only completed 5-minute bars through 10:30 ET; the engine enters no earlier than the next bar open.

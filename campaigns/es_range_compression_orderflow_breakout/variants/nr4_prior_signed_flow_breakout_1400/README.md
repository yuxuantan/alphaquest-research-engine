# nr4_prior_signed_flow_breakout_1400

Campaign: `es_range_compression_orderflow_breakout`

Mechanic: NR4 prior-session high/low breakout with same-bar total signed-flow confirmation through 14:00 ET.

Why this expresses the edge: NR4 compression defines the prior volatility-contraction state; the breakout reference defines the price-action trigger; the aggregate-flow condition requires participation on the completed breakout bar.

Entry module: `range_compression_orderflow_breakout`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

Parameter grid: `entry.params.min_breakout_ticks` x `entry.params.min_orderflow_imbalance` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 81 combinations.

Lookahead controls: prior compression, opening range, breakout close, and flow confirmation are completed before signal; the engine enters no earlier than next bar open.

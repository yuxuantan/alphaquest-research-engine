# late_lunch_1200_1330_signed_breakout_1500

Mechanic: completed 12:00-13:30 ET late-lunch range breakout with total signed-flow confirmation through 15:00 ET. Signals use only the completed midday range and completed confirmation bar; fills are next-bar open.

Entry tunables: `max_range_points` and `min_orderflow_imbalance`. Stop tunable: `stop_offset_ticks`. Target tunable: `target_r_multiple`. Total grid: 81 combinations.

Lookahead controls: the range high/low are unavailable until `13:30:00` ET, the confirmation bar must close before signal generation, and the backtest engine enters no earlier than the next bar open.

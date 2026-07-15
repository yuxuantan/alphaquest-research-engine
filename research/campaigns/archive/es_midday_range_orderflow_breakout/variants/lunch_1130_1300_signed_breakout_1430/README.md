# lunch_1130_1300_signed_breakout_1430

Mechanic: completed 11:30-13:00 ET lunch range breakout with total signed-flow confirmation through 14:30 ET. Signals use only the completed midday range and completed confirmation bar; fills are next-bar open.

Entry tunables: `max_range_points` and `min_orderflow_imbalance`. Stop tunable: `stop_offset_ticks`. Target tunable: `target_r_multiple`. Total grid: 81 combinations.

Lookahead controls: the range high/low are unavailable until `13:00:00` ET, the confirmation bar must close before signal generation, and the backtest engine enters no earlier than the next bar open.

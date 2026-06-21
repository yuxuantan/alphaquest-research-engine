# late_lunch_1200_1330_large10_breakout_1500

Mechanic: completed 12:00-13:30 ET late-lunch range breakout with large-10 signed-flow confirmation through 15:00 ET. Signals use only the completed midday range and completed confirmation bar; fills are next-bar open.

Entry tunables: `max_range_points` and `min_orderflow_imbalance`. Stop tunable: `stop_offset_ticks`. Target tunable: `target_r_multiple`. Total grid: 81 combinations.

Lookahead controls: the range high/low are unavailable until `13:30:00` ET, the confirmation bar must close before signal generation, and the backtest engine enters no earlier than the next bar open.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_midday_range_orderflow_breakout/late_lunch_1200_1330_large10_breakout_1500/run1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.

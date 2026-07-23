# classic_turn_window_1000_long

This variant goes long during a predeclared first-days-or-last-days calendar turn-of-month window. The signal is evaluated on the completed 09:55-10:00 ET 5-minute bar, enters on the next bar open, and flattens at 15:55 ET unless stop or target is hit.

Tunable parameters are fixed before testing: first calendar days, last calendar days, percent stop, and fixed-R target.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_turn_of_month_seasonality/classic_turn_window_1000_long/rescue1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.

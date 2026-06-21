# twenty_day_trend_1000_two_sided

This variant trades the sign of the prior close-to-close ES trend over short/intermediate lookbacks after the completed 10:00 ET 5-minute bar. The signal uses prior completed RTH closes only, enters on the next bar open, and flattens same day.

Tunable parameters are fixed before testing: two entry parameters, one percent stop, and one fixed-R target.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_daily_time_series_momentum/twenty_day_trend_1000_two_sided/rescue1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.

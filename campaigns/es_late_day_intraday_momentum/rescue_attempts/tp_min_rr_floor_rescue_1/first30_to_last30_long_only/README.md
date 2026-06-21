# first30_to_last30_long_only

This variant keeps the same first-30-minute-to-last-30-minute momentum mechanic but isolates the long side. It trades only when the completed first window is positive versus the previous RTH close.

Tunable parameters are fixed before testing: one entry threshold, one percent stop, and one fixed-R target.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_late_day_intraday_momentum/first30_to_last30_long_only/rescue1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.

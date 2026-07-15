# month_end_last_days_1000_long

This variant isolates the month-end side of the turn-of-month effect. It goes long only during the configured final calendar days of a month after the completed 09:55-10:00 ET 5-minute bar and flattens by 15:55 ET.

Tunable parameters are fixed before testing: last calendar days, percent stop, and fixed-R target.


## stop_distance_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_turn_of_month_seasonality/month_end_last_days_1000_long/run1`. Only stop distance was widened by 1.5x; entry, target/exit, data, costs, fills, sessions, and validation gates are unchanged.

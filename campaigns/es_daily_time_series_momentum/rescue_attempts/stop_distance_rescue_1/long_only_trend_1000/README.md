# long_only_trend_1000

This variant tests the long side of ES close-to-close time-series momentum while preserving the same prior-trend signal family. The signal uses prior completed RTH closes only, enters on the next bar open, and flattens same day.

Tunable parameters are fixed before testing: two entry parameters, one percent stop, and one fixed-R target.


## stop_distance_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_daily_time_series_momentum/long_only_trend_1000/rescue1`. Only stop distance was widened by 1.5x; entry, target/exit, data, costs, fills, sessions, and validation gates are unchanged.

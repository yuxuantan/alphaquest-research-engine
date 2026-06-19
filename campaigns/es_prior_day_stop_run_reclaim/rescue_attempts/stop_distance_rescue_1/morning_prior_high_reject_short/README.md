# morning_prior_high_reject_short

This variant isolates the short side of the prior-day stop-run reclaim edge in
the morning. From 09:35 through 11:30 ET, it enters short only after a completed
5-minute bar sweeps the prior RTH high and closes back below that level.

Tunable parameters are fixed before testing: reclaim window, minimum volume
ratio, percent stop, and fixed-R target.


## stop_distance_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_prior_day_stop_run_reclaim/morning_prior_high_reject_short/rescue1`. Only stop distance was widened by 1.5x; entry, target/exit, data, costs, fills, sessions, and validation gates are unchanged.

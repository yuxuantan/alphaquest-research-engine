# first30_penultimate_alignment

This variant requires the first-30-minute return direction and the completed 15:00-15:30 ET penultimate window direction to align before entering for the late-day window. It tests whether same-day continuation is stronger when late-session pressure has not reversed before the signal.

Tunable parameters are fixed before testing: two entry thresholds, one percent stop, and one fixed-R target.


## stop_distance_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_late_day_intraday_momentum/first30_penultimate_alignment/rescue1`. Only stop distance was widened by 1.5x; entry, target/exit, data, costs, fills, sessions, and validation gates are unchanged.

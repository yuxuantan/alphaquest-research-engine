# morning_prior_low_reclaim_long

This variant isolates the long side of the prior-day stop-run reclaim edge in
the morning. From 09:35 through 11:30 ET, it enters long only after a completed
5-minute bar sweeps the prior RTH low and closes back above that level.

Tunable parameters are fixed before testing: reclaim window, minimum volume
ratio, percent stop, and fixed-R target.

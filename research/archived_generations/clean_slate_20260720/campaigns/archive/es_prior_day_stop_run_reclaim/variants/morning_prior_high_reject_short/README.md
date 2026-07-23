# morning_prior_high_reject_short

This variant isolates the short side of the prior-day stop-run reclaim edge in
the morning. From 09:35 through 11:30 ET, it enters short only after a completed
5-minute bar sweeps the prior RTH high and closes back below that level.

Tunable parameters are fixed before testing: reclaim window, minimum volume
ratio, percent stop, and fixed-R target.

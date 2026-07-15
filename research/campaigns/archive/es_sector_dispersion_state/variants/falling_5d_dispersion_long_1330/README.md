# falling_5d_dispersion_long_1330

Mechanic: at 13:30 ET, buy ES when the one-business-day-lagged 5-day change in realized cross-sector return dispersion ranks in the lower tail of its trailing 252 observations.

Entry uses `sector_dispersion_state`; stop uses `percent_from_entry`; target uses `fixed_r`. The only entry tunable is `entry.params.rank_max`; stop and target each have one tunable.

Lookahead control: the dispersion-change feature is based on ETF adjusted closes available no later than the prior business day. The ES signal uses the completed 13:29 bar and the engine enters at the next bar open.

# high_1d_dispersion_short_1000

Mechanic: at 10:00 ET, short ES when the one-business-day-lagged 1-day realized cross-sector return dispersion ranks in the upper tail of its trailing 252 observations.

Entry uses `sector_dispersion_state`; stop uses `percent_from_entry`; target uses `fixed_r`. The only entry tunable is `entry.params.rank_min`; stop and target each have one tunable.

Lookahead control: the sector-dispersion feature is based on ETF adjusted closes available no later than the prior business day. The ES signal uses the completed 09:59 bar and the engine enters at the next bar open.


Rescue attempt 1: parameter-space-only rescue. Mechanics, entry time, modules, data, costs, sessions, and validation gates are unchanged. The rescue tightens the dispersion threshold and changes only stop/target parameter grids.

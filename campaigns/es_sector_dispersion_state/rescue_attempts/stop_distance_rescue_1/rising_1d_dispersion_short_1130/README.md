# rising_1d_dispersion_short_1130

Mechanic: at 11:30 ET, short ES when the one-business-day-lagged 1-day change in realized cross-sector return dispersion ranks in the upper tail of its trailing 252 observations.

Entry uses `sector_dispersion_state`; stop uses `percent_from_entry`; target uses `fixed_r`. The only entry tunable is `entry.params.rank_min`; stop and target each have one tunable.

Lookahead control: the dispersion-change feature is based on ETF adjusted closes available no later than the prior business day. The ES signal uses the completed 11:29 bar and the engine enters at the next bar open.


Rescue attempt 1: parameter-space-only rescue. Mechanics, entry time, modules, data, costs, sessions, and validation gates are unchanged. The rescue tightens the dispersion threshold and changes only stop/target parameter grids.


## stop_distance_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_sector_dispersion_state/rising_1d_dispersion_short_1130/rescue1`. Only stop distance was widened by 1.5x; entry, target/exit, data, costs, fills, sessions, and validation gates are unchanged.

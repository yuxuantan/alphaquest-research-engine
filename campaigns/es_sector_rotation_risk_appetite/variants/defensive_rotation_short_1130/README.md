# defensive_rotation_short_1130

Mechanic: at 11:30 ET, short ES when the one-business-day-lagged 5-day return spread of cyclical sectors over defensive sectors ranks in the lower tail, indicating persistent defensive rotation.

Entry uses `sector_rotation_risk_appetite`; stop uses `percent_from_entry`; target uses `fixed_r`. The only entry tunable is `entry.params.rank_max`; stop and target each have one tunable.

Lookahead control: the sector feature is based on ETF adjusted closes available no later than the prior business day. The ES signal uses the completed 11:29 bar and the engine enters at the next bar open.

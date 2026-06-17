# defensive_lead_short_1000

Mechanic: at 10:00 ET, short ES when the one-business-day-lagged 1-day return spread of cyclical sectors over defensive sectors ranks in the lower tail, indicating defensive leadership.

Entry uses `sector_rotation_risk_appetite`; stop uses `percent_from_entry`; target uses `fixed_r`. The only entry tunable is `entry.params.rank_max`; stop and target each have one tunable.

Lookahead control: the sector feature is based on ETF adjusted closes available no later than the prior business day. The ES signal uses the completed 09:59 bar and the engine enters at the next bar open.

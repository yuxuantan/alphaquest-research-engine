# growth_lead_long_1030

Mechanic: at 10:30 ET, buy ES when the one-business-day-lagged 5-day return spread of growth sectors (XLK/XLY) over defensive sectors ranks in the upper tail.

Entry uses `sector_rotation_risk_appetite`; stop uses `percent_from_entry`; target uses `fixed_r`. The only entry tunable is `entry.params.rank_min`; stop and target each have one tunable.

Lookahead control: the sector feature is based on ETF adjusted closes available no later than the prior business day. The ES signal uses the completed 10:29 bar and the engine enters at the next bar open.

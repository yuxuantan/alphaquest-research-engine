# cyclical_lead_long_1000

Mechanic: at 10:00 ET, buy ES when the one-business-day-lagged 1-day return spread of cyclical sectors (XLY/XLF/XLI/XLK) over defensive sectors (XLP/XLU/XLV) ranks in the upper tail of its trailing 252 observations.

Entry uses `sector_rotation_risk_appetite`; stop uses `percent_from_entry`; target uses `fixed_r`. The only entry tunable is `entry.params.rank_min`; stop and target each have one tunable.

Lookahead control: the sector feature is based on ETF adjusted closes available no later than the prior business day. The ES signal uses the completed 09:59 bar and the engine enters at the next bar open.

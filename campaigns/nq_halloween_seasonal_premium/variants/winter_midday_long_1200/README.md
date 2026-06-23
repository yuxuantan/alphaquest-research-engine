# winter_midday_long_1200

Campaign: `nq_halloween_seasonal_premium`

Mechanic: At 12:00 ET during November-April, buy NQ at the next bar boundary and flatten by 15:55 ET unless stop or target is hit.

No feature file is required; the signal uses only known calendar month and completed-bar timing.

Entry module: `halloween_seasonal_premium`; stop module: `percent_from_entry`; target module: `fixed_r`.

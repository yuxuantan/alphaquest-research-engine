# preholiday_open_long_1000

Campaign: `nq_preholiday_effect`

Entry module: `preholiday_effect`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

Mechanic: At 10:00 ET on the last regular RTH session before a full NYSE holiday, enter long NQ at next bar open and flatten by 15:55 ET unless stop or target is hit.

Source ES config: `campaigns/es_preholiday_effect/variants/preholiday_open_long_1000/config.yaml`

Lookahead controls: signal dates come only from `data/external/nyse_preholiday_regular_sessions_20110103_20260609.csv`; the strategy uses the completed signal bar and enters at the next bar open. It does not use future holiday-week returns, future high/low, future volume, or overnight exposure.

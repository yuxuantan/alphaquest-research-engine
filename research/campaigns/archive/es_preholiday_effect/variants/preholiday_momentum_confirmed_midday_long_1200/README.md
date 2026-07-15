# preholiday_momentum_confirmed_midday_long_1200

Campaign: `es_preholiday_effect`

Entry module: `preholiday_effect`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

Mechanic: At 12:00 ET on the last regular RTH session before a full NYSE holiday, enter long ES only if the completed RTH return is at least the configured threshold; flatten by 15:55 ET unless stop or target is hit.

Parameter combinations: `27`. Tunables are declared before testing and limited to the configured entry filter, stop percentage, and fixed-R target.

Lookahead controls: signal dates come only from `data/external/nyse_preholiday_regular_sessions_20110103_20260609.csv`; the strategy uses the completed signal bar and enters at the next bar open. It does not use future holiday-week returns, future high/low, future volume, or overnight exposure.

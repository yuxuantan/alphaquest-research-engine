# santa_window_open_long_1000

Campaign: `es_turn_of_year_effect`

Entry module: `turn_of_year_effect`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

Mechanic: At 10:00 ET during the turn-of-year window, enter long ES at next bar open and flatten by 15:55 ET unless stop or target is hit.

Parameter combinations: `9`. Tunables are declared before testing and limited to the configured entry filter, stop percentage, and fixed-R target.

Lookahead controls: signal dates come only from `data/external/nyse_turn_of_year_sessions_20110103_20260609.csv`; the strategy uses the completed signal bar and enters at the next bar open. It does not use future turn-of-year returns, future high/low, future volume, or overnight exposure.

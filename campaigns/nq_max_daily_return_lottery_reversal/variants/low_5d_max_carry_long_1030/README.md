# low_5d_max_carry_long_1030

Mechanic: At 10:30 ET, long NQ when the prior 5-session maximum daily return rank is in the low tail.

The signal state is read from `data/external/nq_max_daily_return_features_20110103_20260612.csv`. Every tradable MAX field is shifted one completed NQ RTH session, so the signal date cannot use the current session's daily return or final session values. Entry is evaluated on the completed 1-minute bar immediately before `10:30:00`.

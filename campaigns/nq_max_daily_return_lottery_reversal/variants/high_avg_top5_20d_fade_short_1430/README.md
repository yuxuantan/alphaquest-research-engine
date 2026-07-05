# high_avg_top5_20d_fade_short_1430

Mechanic: At 14:30 ET, short NQ when the prior 20-session average of the five largest daily returns ranks in the high tail.

The signal state is read from `data/external/nq_max_daily_return_features_20110103_20260612.csv`. Every tradable MAX field is shifted one completed NQ RTH session, so the signal date cannot use the current session's daily return or final session values. Entry is evaluated on the completed 1-minute bar immediately before `14:30:00`.

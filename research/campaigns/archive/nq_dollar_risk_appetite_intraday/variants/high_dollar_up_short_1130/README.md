# high_dollar_up_short_1130

Mechanic: At 11:30 ET, short NQ when prior-business-day broad dollar level and one-day return ranks are both elevated.

Signal state is computed from `data/external/nq_dollar_risk_appetite_features_20110103_20260612.csv`, where every session uses only the latest FRED DTWEXBGS observation available at least one business day before the NQ session. The entry signal is evaluated on the completed 1-minute bar immediately before the configured entry time, so fills occur no earlier than the next bar open.

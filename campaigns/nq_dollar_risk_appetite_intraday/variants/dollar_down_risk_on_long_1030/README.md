# dollar_down_risk_on_long_1030

Mechanic: At 10:30 ET, long NQ when the prior-business-day broad dollar one-day return ranks in the lower tail.

Signal state is computed from `data/external/nq_dollar_risk_appetite_features_20110103_20260612.csv`, where every session uses only the latest FRED DTWEXBGS observation available at least one business day before the NQ session. The entry signal is evaluated on the completed 1-minute bar immediately before the configured entry time, so fills occur no earlier than the next bar open.

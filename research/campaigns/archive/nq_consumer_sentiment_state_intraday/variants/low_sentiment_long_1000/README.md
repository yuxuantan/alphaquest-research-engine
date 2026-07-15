# low_sentiment_long_1000

Mechanic: At 10:00 ET, buy NQ when 45-day-lagged University of Michigan consumer sentiment rank is in the lower tail, expressing pessimism/risk-premium rebound.

Feature timing: `data/external/nq_consumer_sentiment_features_20110103_20260612.csv` uses the latest UMCSENT observation available at least 45 calendar days before the NQ session date.

Entry module: `consumer_sentiment_state`; stop module: `percent_from_entry`; target module: `fixed_r`.

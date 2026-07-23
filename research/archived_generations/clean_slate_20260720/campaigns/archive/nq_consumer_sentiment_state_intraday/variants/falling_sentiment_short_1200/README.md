# falling_sentiment_short_1200

Mechanic: At 12:00 ET, short NQ when 45-day-lagged three-month consumer-sentiment change rank is in the lower tail, expressing deteriorating household sentiment.

Feature timing: `data/external/nq_consumer_sentiment_features_20110103_20260612.csv` uses the latest UMCSENT observation available at least 45 calendar days before the NQ session date.

Entry module: `consumer_sentiment_state`; stop module: `percent_from_entry`; target module: `fixed_r`.

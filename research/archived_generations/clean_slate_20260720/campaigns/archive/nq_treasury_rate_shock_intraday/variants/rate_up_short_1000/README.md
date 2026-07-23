# rate_up_short_1000

Mechanic: At 10:00 ET, short NQ when the latest prior Treasury 10-year one-day yield-change rank is in the upper tail.

Signal state is computed from `data/external/nq_treasury_rate_state_features_20110103_20260612.csv`, where each NQ session uses only Treasury observations strictly before the session date. The entry signal is evaluated on the completed 1-minute bar immediately before the configured entry time, so fills occur no earlier than the next bar open.

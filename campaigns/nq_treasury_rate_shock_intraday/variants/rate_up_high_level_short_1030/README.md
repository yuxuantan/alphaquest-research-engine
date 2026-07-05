# rate_up_high_level_short_1030

Mechanic: At 10:30 ET, short NQ when prior 10-year yield-change rank is high and the 10-year level rank is also elevated.

Signal state is computed from `data/external/nq_treasury_rate_state_features_20110103_20260612.csv`, where each NQ session uses only Treasury observations strictly before the session date. The entry signal is evaluated on the completed 1-minute bar immediately before the configured entry time, so fills occur no earlier than the next bar open.

# bull_flattening_long_1130

Mechanic: At 11:30 ET, long NQ when prior 10-year yield-change rank and 10y-2y curve-change rank are both low.

Signal state is computed from `data/external/nq_treasury_rate_state_features_20110103_20260612.csv`, where each NQ session uses only Treasury observations strictly before the session date. The entry signal is evaluated on the completed 1-minute bar immediately before the configured entry time, so fills occur no earlier than the next bar open.

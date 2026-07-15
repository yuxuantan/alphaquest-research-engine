# ma_distance_contrarian_1400

Mechanic: At 14:00 ET, trade NQ contrarian to the latest available NAAIM exposure distance from its 26-observation moving average.

Signal state is computed from `data/external/nq_naaim_exposure_features_20110103_20260612.csv`, where each observation is mapped to the first NQ RTH session at least two business days after the NAAIM observation date. The entry signal is evaluated on the completed 1-minute bar immediately before the configured entry time, so fills occur no earlier than the next bar open.

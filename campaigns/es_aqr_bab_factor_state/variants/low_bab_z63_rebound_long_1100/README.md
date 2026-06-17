# low_bab_z63_rebound_long_1100

Mechanic: At 11:00 ET, long ES when the lagged AQR USA BAB 63-observation z-score rank is in the lower tail; flatten by 15:55 ET unless stop or target is hit.

Signal state is computed from `data/external/es_aqr_bab_features_20110103_20260609.csv`. Each ES session uses only the latest AQR BAB observation at least 45 calendar days old because AQR's public daily BAB dataset is updated monthly. The entry signal is evaluated on the completed 1-minute bar immediately before the configured entry time, so fills occur no earlier than the next bar open.

Stop module: `percent_from_entry`. Target module: `fixed_r`. No overnight exposure is allowed.

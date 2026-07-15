# strong_yen_short_1130

Campaign: `es_usdjpy_safe_haven_spillover`

Mechanic: At 11:30 ET, short ES when the lagged USD/JPY level rank is in the lower tail, indicating a strong-yen safe-haven state; flatten by 15:55.

Feature timing: `data/external/es_usdjpy_safe_haven_features_20110103_20260609.csv` uses the latest FRED DEXJPUS USD/JPY observation available no later than one business day before the ES session. Signals are evaluated on a completed 1-minute bar and entered by the engine on the next bar.

Entry module: `usdjpy_safe_haven`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

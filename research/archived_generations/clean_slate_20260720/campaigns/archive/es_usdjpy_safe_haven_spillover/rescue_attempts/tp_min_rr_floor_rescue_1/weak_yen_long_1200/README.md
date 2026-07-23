# weak_yen_long_1200

Campaign: `es_usdjpy_safe_haven_spillover`

Mechanic: At 12:00 ET, buy ES when the lagged USD/JPY level rank is in the upper tail, indicating weak-yen carry/risk appetite; flatten by 15:55.

Feature timing: `data/external/es_usdjpy_safe_haven_features_20110103_20260609.csv` uses the latest FRED DEXJPUS USD/JPY observation available no later than one business day before the ES session. Signals are evaluated on a completed 1-minute bar and entered by the engine on the next bar.

Entry module: `usdjpy_safe_haven`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_usdjpy_safe_haven_spillover/weak_yen_long_1200/rescue1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.

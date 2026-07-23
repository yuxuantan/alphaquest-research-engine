# front_stress_short_1130

Campaign: `es_cboe_vix_term_structure_intraday`

Mechanic: At 11:30:00 ET, short ES when the latest prior VIX9D/VIX ratio rank is in the upper tail; flatten by 15:55 ET unless stop or target is hit.

Feature timing: `data/external/es_cboe_vix_term_structure_features_20110103_20260609.csv` uses the latest Cboe VIX term-structure close strictly before the ES session date.

Entry module: `cboe_vix_term_structure` with setup mode `front_stress_short`.

Stop module: `percent_from_entry`. Target module: `fixed_r`.

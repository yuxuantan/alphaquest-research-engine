# backwardation_short_1000

Campaign: `es_cboe_vix_term_structure_intraday`

Mechanic: At 10:00:00 ET, short ES when the latest prior VIX/VIX3M ratio rank is in the upper tail; flatten by 15:55 ET unless stop or target is hit.

Feature timing: `data/external/es_cboe_vix_term_structure_features_20110103_20260609.csv` uses the latest Cboe VIX term-structure close strictly before the ES session date.

Entry module: `cboe_vix_term_structure` with setup mode `backwardation_short`.

Stop module: `percent_from_entry`. Target module: `fixed_r`.

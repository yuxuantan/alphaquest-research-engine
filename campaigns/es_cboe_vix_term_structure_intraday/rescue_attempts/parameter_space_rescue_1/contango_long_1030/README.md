# contango_long_1030

Campaign: `es_cboe_vix_term_structure_intraday`

Mechanic: At 10:30:00 ET, buy ES when the latest prior VIX/VIX3M ratio rank is in the lower tail; flatten by 15:55 ET unless stop or target is hit.

Feature timing: `data/external/es_cboe_vix_term_structure_features_20110103_20260609.csv` uses the latest Cboe VIX term-structure close strictly before the ES session date.

Entry module: `cboe_vix_term_structure` with setup mode `contango_long`.

Stop module: `percent_from_entry`. Target module: `fixed_r`.

## Rescue Attempt 1
Original contango long failed core with 2/27 profitable combinations; rescue preserves the same contango long mechanic and tests the adjacent lower-tail rank neighborhood with wider stop and higher-R exits around the only profitable original rows.

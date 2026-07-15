# high_short_term_correlation_short_1330

Campaign: `es_cboe_implied_correlation_intraday`

Mechanic: At 13:30:00 ET, short ES when the latest prior COR1M-minus-COR3M term-spread rank is in the upper tail; flatten by 15:55 ET unless stop or target is hit.

Feature timing: `data/external/es_cboe_implied_correlation_features_20110103_20260609.csv` uses the latest Cboe COR1M/COR3M close strictly before the ES session date.

Entry module: `cboe_implied_correlation` with setup mode `high_short_term_correlation_short`.

Stop module: `percent_from_entry`. Target module: `fixed_r`.

Rescue attempt 1: Original high short-term correlation term-spread short failed core with 6/27 profitable combinations; rescue preserves the same term-spread short mechanic and tests the adjacent wide-stop/high-R neighborhood.

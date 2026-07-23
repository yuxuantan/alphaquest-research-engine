# high_cor3m_short_1000

Campaign: `es_cboe_implied_correlation_intraday`

Mechanic: At 10:00:00 ET, short ES when the latest prior Cboe COR3M close rank is in the upper tail; flatten by 15:55 ET unless stop or target is hit.

Feature timing: `data/external/es_cboe_implied_correlation_features_20110103_20260609.csv` uses the latest Cboe COR1M/COR3M close strictly before the ES session date.

Entry module: `cboe_implied_correlation` with setup mode `high_cor3m_short`.

Stop module: `percent_from_entry`. Target module: `fixed_r`.

Rescue attempt 1: Original high-COR3M short failed core with zero profitable combinations; rescue preserves the same high-COR3M short mechanic and tests adjacent thresholds with tighter stop/target ranges.

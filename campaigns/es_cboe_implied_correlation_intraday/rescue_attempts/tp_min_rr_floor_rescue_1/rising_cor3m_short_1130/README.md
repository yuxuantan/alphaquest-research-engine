# rising_cor3m_short_1130

Campaign: `es_cboe_implied_correlation_intraday`

Mechanic: At 11:30:00 ET, short ES when the latest prior Cboe COR3M one-day change rank is in the upper tail; flatten by 15:55 ET unless stop or target is hit.

Feature timing: `data/external/es_cboe_implied_correlation_features_20110103_20260609.csv` uses the latest Cboe COR1M/COR3M close strictly before the ES session date.

Entry module: `cboe_implied_correlation` with setup mode `rising_cor3m_short`.

Stop module: `percent_from_entry`. Target module: `fixed_r`.

Rescue attempt 1: Original rising-COR3M short failed core with zero profitable combinations; rescue preserves the same rising-COR3M short mechanic and tests adjacent thresholds with tighter stop/target ranges.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_cboe_implied_correlation_intraday/rising_cor3m_short_1130/rescue1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.

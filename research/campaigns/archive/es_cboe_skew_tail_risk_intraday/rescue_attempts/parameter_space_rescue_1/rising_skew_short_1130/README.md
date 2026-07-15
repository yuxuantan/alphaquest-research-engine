# rising_skew_short_1130

Campaign: `es_cboe_skew_tail_risk_intraday`

Mechanic: At 11:30:00 ET, short ES when the latest prior Cboe SKEW one-day change rank is in the upper tail; flatten by 15:55 ET unless stop or target is hit.

Feature timing: `data/external/es_cboe_skew_tail_risk_features_20110103_20260609.csv` uses the latest Cboe SKEW close strictly before the ES session date.

Entry module: `cboe_skew_tail_risk` with setup mode `rising_skew_short`.

Stop module: `percent_from_entry`. Target module: `fixed_r`.

Rescue attempt 1: Original rising-SKEW short failed core with zero profitable combinations; rescue preserves the same rising-SKEW short mechanic and tests adjacent change-rank thresholds with tighter stop/target ranges.

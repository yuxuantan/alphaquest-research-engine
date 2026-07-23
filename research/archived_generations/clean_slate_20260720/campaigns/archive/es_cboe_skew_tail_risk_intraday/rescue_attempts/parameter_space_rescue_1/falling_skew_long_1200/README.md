# falling_skew_long_1200

Campaign: `es_cboe_skew_tail_risk_intraday`

Mechanic: At 12:00:00 ET, buy ES when the latest prior Cboe SKEW one-day change rank is in the lower tail; flatten by 15:55 ET unless stop or target is hit.

Feature timing: `data/external/es_cboe_skew_tail_risk_features_20110103_20260609.csv` uses the latest Cboe SKEW close strictly before the ES session date.

Entry module: `cboe_skew_tail_risk` with setup mode `falling_skew_long`.

Stop module: `percent_from_entry`. Target module: `fixed_r`.

Rescue attempt 1: Original falling-SKEW long failed core with zero profitable combinations; rescue preserves the same falling-SKEW long mechanic and tests adjacent change-rank thresholds with tighter stop/target ranges.

# high_skew_short_1000

Campaign: `es_cboe_skew_tail_risk_intraday`

Mechanic: At 10:00:00 ET, short ES when the latest prior Cboe SKEW close rank is in the upper tail; flatten by 15:55 ET unless stop or target is hit.

Feature timing: `data/external/es_cboe_skew_tail_risk_features_20110103_20260609.csv` uses the latest Cboe SKEW close strictly before the ES session date.

Entry module: `cboe_skew_tail_risk` with setup mode `high_skew_short`.

Stop module: `percent_from_entry`. Target module: `fixed_r`.

Rescue attempt 1: Original high-SKEW short failed core with only 2/27 profitable combinations; rescue preserves the same high-SKEW short mechanic and tests adjacent upper-tail thresholds with tighter stop/target ranges.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_cboe_skew_tail_risk_intraday/high_skew_short_1000/rescue1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.

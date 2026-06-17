# persistent_high_skew_short_1330

Campaign: `es_cboe_skew_tail_risk_intraday`

Mechanic: At 13:30:00 ET, short ES when the latest prior five-session Cboe SKEW mean rank is in the upper tail; flatten by 15:55 ET unless stop or target is hit.

Feature timing: `data/external/es_cboe_skew_tail_risk_features_20110103_20260609.csv` uses the latest Cboe SKEW close strictly before the ES session date.

Entry module: `cboe_skew_tail_risk` with setup mode `persistent_high_skew_short`.

Stop module: `percent_from_entry`. Target module: `fixed_r`.

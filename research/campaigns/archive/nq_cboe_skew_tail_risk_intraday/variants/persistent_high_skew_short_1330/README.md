# persistent_high_skew_short_1330

Mechanic: At 13:30 ET, short NQ when the latest prior five-day Cboe SKEW mean rank is in the upper tail, expressing persistent implied downside-tail risk.

Feature timing: `data/external/nq_cboe_skew_tail_risk_features_20110103_20260612.csv` uses the latest Cboe SKEW close strictly before the NQ session date.

Entry module: `cboe_skew_tail_risk`; stop module: `percent_from_entry`; target module: `fixed_r`.

# rising_skew_short_1130

Mechanic: At 11:30 ET, short NQ when the latest prior one-day Cboe SKEW change rank is in the upper tail, expressing abrupt tail-risk repricing.

Feature timing: `data/external/nq_cboe_skew_tail_risk_features_20110103_20260612.csv` uses the latest Cboe SKEW close strictly before the NQ session date.

Entry module: `cboe_skew_tail_risk`; stop module: `percent_from_entry`; target module: `fixed_r`.

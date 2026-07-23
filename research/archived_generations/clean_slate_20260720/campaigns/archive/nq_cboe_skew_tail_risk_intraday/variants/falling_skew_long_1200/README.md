# falling_skew_long_1200

Mechanic: At 12:00 ET, buy NQ when the latest prior one-day Cboe SKEW change rank is in the lower tail, expressing easing tail-risk demand.

Feature timing: `data/external/nq_cboe_skew_tail_risk_features_20110103_20260612.csv` uses the latest Cboe SKEW close strictly before the NQ session date.

Entry module: `cboe_skew_tail_risk`; stop module: `percent_from_entry`; target module: `fixed_r`.

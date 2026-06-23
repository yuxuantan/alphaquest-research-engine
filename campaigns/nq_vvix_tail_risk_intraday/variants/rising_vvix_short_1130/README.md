# rising_vvix_short_1130

Campaign: `nq_vvix_tail_risk_intraday`

Mechanic: At 11:30 ET, short NQ when the latest prior one-day VVIX change rank is in the upper tail, expressing abrupt tail-risk repricing.

Feature timing: `data/external/nq_vvix_tail_risk_features_20110103_20260612.csv` uses the latest Cboe VVIX/VIX close strictly before the NQ session date.

Entry module: `vvix_tail_risk`; stop module: `percent_from_entry`; target module: `fixed_r`.

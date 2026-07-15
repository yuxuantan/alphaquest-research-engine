# low_vvix_long_1030

Campaign: `nq_vvix_tail_risk_intraday`

Mechanic: At 10:30 ET, buy NQ when the latest prior VVIX close rank is in the lower tail, expressing low tail-risk demand through NQ risk appetite.

Feature timing: `data/external/nq_vvix_tail_risk_features_20110103_20260612.csv` uses the latest Cboe VVIX/VIX close strictly before the NQ session date.

Entry module: `vvix_tail_risk`; stop module: `percent_from_entry`; target module: `fixed_r`.

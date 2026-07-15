# high_vvix_vix_ratio_short_1330

Campaign: `nq_vvix_tail_risk_intraday`

Mechanic: At 13:30 ET, short NQ when the latest prior VVIX/VIX ratio rank is elevated, expressing volatility-of-volatility stress beyond VIX level alone.

Feature timing: `data/external/nq_vvix_tail_risk_features_20110103_20260612.csv` uses the latest Cboe VVIX/VIX close strictly before the NQ session date.

Entry module: `vvix_tail_risk`; stop module: `percent_from_entry`; target module: `fixed_r`.

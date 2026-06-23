# low_vix_complacency_short_1030

Campaign: `nq_cboe_vix_level_state_intraday`

Mechanic: At 10:30 ET, short NQ when the latest prior VIX close rank is low, expressing complacency reversal risk.

Feature timing: `data/external/nq_cboe_vix_level_features_20110103_20260612.csv` uses the latest Cboe VIX close strictly before the NQ session date.

Entry module: `cboe_vix_level_state`; stop module: `percent_from_entry`; target module: `fixed_r`.

# vix_spike_riskoff_short_1130

Campaign: `nq_cboe_vix_level_state_intraday`

Mechanic: At 11:30 ET, short NQ when the latest prior one-day VIX change rank is elevated, expressing same-day risk-off pressure after a VIX spike.

Feature timing: `data/external/nq_cboe_vix_level_features_20110103_20260612.csv` uses the latest Cboe VIX close strictly before the NQ session date.

Entry module: `cboe_vix_level_state`; stop module: `percent_from_entry`; target module: `fixed_r`.

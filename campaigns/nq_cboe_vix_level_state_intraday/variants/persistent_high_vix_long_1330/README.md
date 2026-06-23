# persistent_high_vix_long_1330

Campaign: `nq_cboe_vix_level_state_intraday`

Mechanic: At 13:30 ET, buy NQ when the latest prior five-day VIX mean rank is high, expressing risk-premium rebound after persistent stress.

Feature timing: `data/external/nq_cboe_vix_level_features_20110103_20260612.csv` uses the latest Cboe VIX close strictly before the NQ session date.

Entry module: `cboe_vix_level_state`; stop module: `percent_from_entry`; target module: `fixed_r`.

# vix_crush_rebound_long_1200

Campaign: `nq_cboe_vix_level_state_intraday`

Mechanic: At 12:00 ET, buy NQ when the latest prior one-day VIX change rank is low, expressing rebound after volatility compression.

Feature timing: `data/external/nq_cboe_vix_level_features_20110103_20260612.csv` uses the latest Cboe VIX close strictly before the NQ session date.

Entry module: `cboe_vix_level_state`; stop module: `percent_from_entry`; target module: `fixed_r`.

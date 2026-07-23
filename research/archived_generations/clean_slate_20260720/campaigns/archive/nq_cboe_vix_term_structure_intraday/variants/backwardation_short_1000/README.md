# backwardation_short_1000

Campaign: `nq_cboe_vix_term_structure_intraday`

Mechanic: At 10:00 ET, short NQ when lagged VIX/VIX3M ratio rank is in the upper tail, expressing broad risk-off term-structure stress through NQ beta.

Feature timing: `data/external/nq_cboe_vix_term_structure_features_20110103_20260612.csv` uses the latest Cboe VIX term-structure close strictly before the NQ session date.

Entry module: `cboe_vix_term_structure`; stop module: `percent_from_entry`; target module: `fixed_r`.

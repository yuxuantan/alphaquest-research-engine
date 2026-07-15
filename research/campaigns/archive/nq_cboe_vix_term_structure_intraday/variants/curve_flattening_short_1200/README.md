# curve_flattening_short_1200

Campaign: `nq_cboe_vix_term_structure_intraday`

Mechanic: At 12:00 ET, short NQ when lagged VIX3M/VIX6M ratio rank is elevated, expressing medium-term curve flattening as broad index risk stress.

Feature timing: `data/external/nq_cboe_vix_term_structure_features_20110103_20260612.csv` uses the latest Cboe VIX term-structure close strictly before the NQ session date.

Entry module: `cboe_vix_term_structure`; stop module: `percent_from_entry`; target module: `fixed_r`.

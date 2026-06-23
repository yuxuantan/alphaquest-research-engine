# front_stress_short_1130

Campaign: `nq_cboe_vix_term_structure_intraday`

Mechanic: At 11:30 ET, short NQ when lagged VIX9D/VIX ratio rank is elevated, expressing near-term option stress through NQ intraday weakness.

Feature timing: `data/external/nq_cboe_vix_term_structure_features_20110103_20260612.csv` uses the latest Cboe VIX term-structure close strictly before the NQ session date.

Entry module: `cboe_vix_term_structure`; stop module: `percent_from_entry`; target module: `fixed_r`.

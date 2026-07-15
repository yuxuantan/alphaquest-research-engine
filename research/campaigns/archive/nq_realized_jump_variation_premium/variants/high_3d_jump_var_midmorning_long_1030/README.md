# high_3d_jump_var_midmorning_long_1030

Campaign: `nq_realized_jump_variation_premium`

Mechanic: At 10:30 ET, enter long NQ when the three-day mean of lagged realized jump variation ranks high; flatten by 15:55.

Why this expresses the edge: realized jump variation separates discontinuous prior-session NQ risk from continuous variation. This variant uses only shifted prior-session features and a fixed completed-bar decision time.

Feature timing: `data/external/nq_realized_jump_variation_features_20110103_20260612.csv` shifts realized jump variation, bipower variation, signed large-return jump proxies, and rolling ranks by one completed RTH session.

Entry module: `realized_jump_variation_premium`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

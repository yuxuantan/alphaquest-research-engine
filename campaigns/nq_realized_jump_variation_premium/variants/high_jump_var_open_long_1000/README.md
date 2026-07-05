# high_jump_var_open_long_1000

Campaign: `nq_realized_jump_variation_premium`

Mechanic: At 10:00 ET, enter long NQ when the prior completed RTH session's realized jump-variation rank is high; flatten by 15:55.

Why this expresses the edge: realized jump variation separates discontinuous prior-session NQ risk from continuous variation. This variant uses only shifted prior-session features and a fixed completed-bar decision time.

Feature timing: `data/external/nq_realized_jump_variation_features_20110103_20260612.csv` shifts realized jump variation, bipower variation, signed large-return jump proxies, and rolling ranks by one completed RTH session.

Entry module: `realized_jump_variation_premium`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

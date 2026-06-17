# high_jump_share_midmorning_long_1030

Campaign: `es_realized_jump_variation_premium`

Mechanic: At 10:30 ET, enter long ES when lagged jump share is in the high tail. Flatten by 15:55 ET unless stop or target is hit.

Feature timing: `data/external/es_realized_jump_variation_features_20110103_20260609.csv` shifts realized jump variation, bipower variation, signed large-return jump proxies, and rolling ranks by one completed RTH session.

Entry module: `realized_jump_variation_premium`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

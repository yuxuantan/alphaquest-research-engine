# positive_jump_reversal_short_1200

Campaign: `es_realized_jump_variation_premium`

Mechanic: At 12:00 ET, enter short ES after high lagged upside jump variation. Flatten by 15:55 ET unless stop or target is hit.

Feature timing: `data/external/es_realized_jump_variation_features_20110103_20260609.csv` shifts realized jump variation, bipower variation, signed large-return jump proxies, and rolling ranks by one completed RTH session.

Entry module: `realized_jump_variation_premium`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

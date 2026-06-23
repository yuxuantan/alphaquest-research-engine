# high_goodvol_fade_short_1200

Campaign: `nq_realized_semivariance_asymmetry`

Mechanic: At 12:00:00 ET, short NQ after a high prior upside-semivariance state, testing whether good volatility is overpaid intraday; flatten by 15:55 unless stop/target is hit.

Feature timing: `data/external/nq_realized_semivariance_features_20110103_20260612.csv` is shifted one completed RTH session.

Entry module: `realized_semivariance_asymmetry`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

# high_downside_share_rebound_long_1130

Campaign: `nq_realized_semivariance_asymmetry`

Mechanic: At 11:30:00 ET, long NQ after a high prior downside-share state, testing compensation after downside volatility dominance; flatten by 15:55 unless stop/target is hit.

Feature timing: `data/external/nq_realized_semivariance_features_20110103_20260612.csv` is shifted one completed RTH session.

Entry module: `realized_semivariance_asymmetry`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

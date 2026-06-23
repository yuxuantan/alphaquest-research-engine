# high_1d_badvol_rebound_long_1000

Campaign: `nq_realized_semivariance_asymmetry`

Mechanic: At 10:00:00 ET, long NQ after a high prior-session downside-semivariance state, testing bad-volatility rebound compensation; flatten by 15:55 unless stop/target is hit.

Feature timing: `data/external/nq_realized_semivariance_features_20110103_20260612.csv` is shifted one completed RTH session.

Entry module: `realized_semivariance_asymmetry`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

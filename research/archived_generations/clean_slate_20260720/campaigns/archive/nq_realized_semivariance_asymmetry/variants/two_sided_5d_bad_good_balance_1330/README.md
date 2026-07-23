# two_sided_5d_bad_good_balance_1330

Campaign: `nq_realized_semivariance_asymmetry`

Mechanic: At 13:30:00 ET, two-sided NQ exposure when the prior five-day semivariance balance rank is in either tail; flatten by 15:55 unless stop/target is hit.

Feature timing: `data/external/nq_realized_semivariance_features_20110103_20260612.csv` is shifted one completed RTH session.

Entry module: `realized_semivariance_asymmetry`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

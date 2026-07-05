# low_1d_vov_calm_long_1130

Mechanic: At 11:30 ET, long NQ when the prior completed RTH session's realized volatility-of-volatility rank is in the low tail; flatten by 15:55 ET unless stop or target is hit.

Signal state is computed from `data/external/nq_realized_vol_of_vol_features_20110103_20260612.csv`, where every tradable realized volatility-of-volatility field is shifted one completed RTH session. The entry signal is evaluated on the completed 1-minute bar immediately before the configured entry time, so fills occur no earlier than the next bar open.

Stop module: `percent_from_entry`. Target module: `fixed_r`. No overnight exposure is allowed.

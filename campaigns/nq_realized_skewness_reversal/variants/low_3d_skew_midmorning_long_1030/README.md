# low_3d_skew_midmorning_long_1030

Campaign: `nq_realized_skewness_reversal`

Mechanic: At 10:30 ET, enter long NQ when the prior 3-session mean realized-skewness rank is in the low tail; flatten by 15:55 ET unless stop or target is hit.

Feature timing: `data/external/nq_lagged_realized_skewness_features_20110103_20260612.csv` is shifted one RTH session, so the skewness state is known before the signal session.

Entry module: `realized_skewness_reversal` with direction mode `low_long`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

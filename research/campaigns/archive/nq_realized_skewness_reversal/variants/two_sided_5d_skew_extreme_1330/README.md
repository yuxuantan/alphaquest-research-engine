# two_sided_5d_skew_extreme_1330

Campaign: `nq_realized_skewness_reversal`

Mechanic: At 13:30 ET, enter long NQ when the prior 5-session mean realized-skewness rank is in the low tail, or short NQ when it is in the high tail; flatten by 15:55 ET unless stop or target is hit.

Feature timing: `data/external/nq_lagged_realized_skewness_features_20110103_20260612.csv` is shifted one RTH session, so the skewness state is known before the signal session.

Entry module: `realized_skewness_reversal` with direction mode `two_sided_extreme`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

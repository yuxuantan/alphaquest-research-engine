# two_sided_5d_skew_extreme_1330

Campaign: `es_realized_skewness_reversal`

Mechanic: At 13:30 ET, enter long ES when the prior 5-session mean realized-skewness rank is in the low tail, or short ES when it is in the high tail; flatten by 15:55 ET unless stop or target is hit.

Feature timing: `data/external/es_lagged_realized_skewness_features_20110103_20260609.csv` is shifted one RTH session, so the skewness state is known before the signal session.

Entry module: `realized_skewness_reversal` with direction mode `two_sided_extreme`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

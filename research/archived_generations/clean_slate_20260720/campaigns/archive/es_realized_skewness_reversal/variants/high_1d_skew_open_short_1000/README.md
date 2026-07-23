# high_1d_skew_open_short_1000

Campaign: `es_realized_skewness_reversal`

Mechanic: At 10:00 ET, enter short ES when the prior completed RTH session's realized-skewness rank is in the high tail; flatten by 15:55 ET unless stop or target is hit.

Feature timing: `data/external/es_lagged_realized_skewness_features_20110103_20260609.csv` is shifted one RTH session, so the skewness state is known before the signal session.

Entry module: `realized_skewness_reversal` with direction mode `high_short`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

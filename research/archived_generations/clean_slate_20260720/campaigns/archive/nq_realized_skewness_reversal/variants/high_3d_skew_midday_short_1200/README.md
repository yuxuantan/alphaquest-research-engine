# high_3d_skew_midday_short_1200

Campaign: `nq_realized_skewness_reversal`

Mechanic: At 12:00 ET, enter short NQ when the prior 3-session mean realized-skewness rank is in the high tail; flatten by 15:55 ET unless stop or target is hit.

Feature timing: `data/external/nq_lagged_realized_skewness_features_20110103_20260612.csv` is shifted one RTH session, so the skewness state is known before the signal session.

Entry module: `realized_skewness_reversal` with direction mode `high_short`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

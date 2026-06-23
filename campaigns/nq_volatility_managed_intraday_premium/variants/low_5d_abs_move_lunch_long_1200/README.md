# low_5d_abs_move_lunch_long_1200

Campaign: `nq_volatility_managed_intraday_premium`

Mechanic: At 12:00 ET, enter long NQ only when the prior-session 5-day average absolute-return rank is at or below the configured threshold; flatten by 15:55 ET unless stop or target is hit.

Feature timing: `data/external/nq_lagged_volatility_features_20110103_20260612.csv` is shifted one RTH session, so the volatility state is known before the signal session.

Pre-PnL density: NQ absret5_rank_252 <= 0.25/0.35/0.45 produced about 65/89/110 candidate sessions per year before execution filters.

Entry module: `volatility_managed_intraday_premium`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

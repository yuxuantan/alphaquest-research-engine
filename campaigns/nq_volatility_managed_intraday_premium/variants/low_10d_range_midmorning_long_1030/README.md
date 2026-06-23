# low_10d_range_midmorning_long_1030

Campaign: `nq_volatility_managed_intraday_premium`

Mechanic: At 10:30 ET, enter long NQ only when the prior-session 10-day average RTH range rank is at or below the configured threshold; flatten by 15:55 ET unless stop or target is hit.

Feature timing: `data/external/nq_lagged_volatility_features_20110103_20260612.csv` is shifted one RTH session, so the volatility state is known before the signal session.

Pre-PnL density: NQ range10_rank_252 <= 0.25/0.35/0.45 produced about 71/90/113 candidate sessions per year before execution filters.

Entry module: `volatility_managed_intraday_premium`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

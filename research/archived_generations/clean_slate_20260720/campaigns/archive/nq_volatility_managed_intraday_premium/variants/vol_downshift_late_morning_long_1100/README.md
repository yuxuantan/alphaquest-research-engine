# vol_downshift_late_morning_long_1100

Campaign: `nq_volatility_managed_intraday_premium`

Mechanic: At 11:00 ET, enter long NQ only when prior 5-day realized volatility is no more than the configured ratio of prior 20-day realized volatility; flatten by 15:55 ET unless stop or target is hit.

Feature timing: `data/external/nq_lagged_volatility_features_20110103_20260612.csv` is shifted one RTH session, so the volatility state is known before the signal session.

Pre-PnL density: NQ vol5_over_vol20 <= 0.60/0.70/0.80 produced about 57/82/111 candidate sessions per year before execution filters.

Entry module: `volatility_managed_intraday_premium`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

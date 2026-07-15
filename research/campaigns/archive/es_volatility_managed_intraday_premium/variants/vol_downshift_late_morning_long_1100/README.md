# vol_downshift_late_morning_long_1100

Campaign: `es_volatility_managed_intraday_premium`

Mechanic: At 11:00 ET, enter long ES only when prior 5-day realized volatility is no more than the configured ratio of prior 20-day realized volatility; flatten by 15:55 ET unless stop or target is hit.

Feature timing: `data/external/es_lagged_volatility_features_20110103_20260609.csv` is shifted one RTH session, so the volatility state is known before the signal session.

Entry module: `volatility_managed_intraday_premium` with setup mode `vol_downshift_long`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

# low_downside20_afternoon_long_1330

Campaign: `es_volatility_managed_intraday_premium`

Mechanic: At 13:30 ET, enter long ES only when the prior-session 20-day downside-semivolatility rank is at or below the configured threshold; flatten by 15:55 ET unless stop or target is hit.

Feature timing: `data/external/es_lagged_volatility_features_20110103_20260609.csv` is shifted one RTH session, so the volatility state is known before the signal session.

Entry module: `volatility_managed_intraday_premium` with setup mode `low_downside20_long`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

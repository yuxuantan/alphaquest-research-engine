# high_vrp_ratio_midday_long_1200

Campaign: `es_variance_risk_premium_intraday`

Mechanic: At 12:00 ET, enter long ES when the lagged implied/realized variance ratio rank is high; flatten by 15:55.

Feature timing: `data/external/es_variance_risk_premium_features_20110103_20260609.csv` uses Cboe VIX close and ES realized variance shifted one completed RTH session, so the VRP state is known before the signal session.

Entry module: `variance_risk_premium_intraday` with setup mode `high_vrp_ratio_long`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

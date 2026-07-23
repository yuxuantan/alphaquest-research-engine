# vrp_rising_afternoon_long_1330

Campaign: `es_variance_risk_premium_intraday`

Mechanic: At 13:30 ET, enter long ES when the lagged 5-session VRP change rank is high; flatten by 15:55.

Feature timing: `data/external/es_variance_risk_premium_features_20110103_20260609.csv` uses Cboe VIX close and ES realized variance shifted one completed RTH session, so the VRP state is known before the signal session.

Entry module: `variance_risk_premium_intraday` with setup mode `vrp_rising_long`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

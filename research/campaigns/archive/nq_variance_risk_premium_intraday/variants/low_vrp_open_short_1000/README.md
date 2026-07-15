# low_vrp_open_short_1000

Campaign: `nq_variance_risk_premium_intraday`

Mechanic: At 10:00 ET, enter short NQ when the lagged variance-risk-premium rank is in the low tail; flatten by 15:55.

Feature timing: `data/external/nq_variance_risk_premium_features_20110103_20260612.csv` uses Cboe VIX close and NQ realized variance shifted one completed RTH session, so the VRP state is known before the signal session.

Entry module: `variance_risk_premium_intraday` with setup mode `low_vrp_short`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

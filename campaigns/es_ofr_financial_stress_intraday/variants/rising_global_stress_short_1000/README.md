# rising_global_stress_short_1000

Campaign: `es_ofr_financial_stress_intraday`

Mechanic: At 10:00 ET, enter short ES when the lagged OFR FSI one-day change rank is in the upper stress-increase tail; flatten by 15:55 ET unless stop or target is hit.

Feature timing: `data/external/es_ofr_financial_stress_features_20110103_20260609.csv` uses the latest OFR observation on or before the session date minus two business days.

Entry module: `ofr_financial_stress`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

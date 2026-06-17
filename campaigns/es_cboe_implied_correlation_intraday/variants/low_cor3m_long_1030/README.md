# low_cor3m_long_1030

Campaign: `es_cboe_implied_correlation_intraday`

Mechanic: At 10:30:00 ET, buy ES when the latest prior Cboe COR3M close rank is in the lower tail; flatten by 15:55 ET unless stop or target is hit.

Feature timing: `data/external/es_cboe_implied_correlation_features_20110103_20260609.csv` uses the latest Cboe COR1M/COR3M close strictly before the ES session date.

Entry module: `cboe_implied_correlation` with setup mode `low_cor3m_long`.

Stop module: `percent_from_entry`. Target module: `fixed_r`.

# rate_down_long_1000

Campaign: `es_treasury_rate_shock_intraday`

Mechanic: At 10:00 ET, go long ES when the latest strictly prior Treasury DGS10 one-observation change ranks in the lower tail; flatten by 15:55.

Feature timing: `data/external/es_treasury_rate_state_features_20110103_20260609.csv` maps each ES session to a Treasury observation date earlier than the ES session date.

Entry module: `treasury_rate_state` with setup mode `rate_down_long`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

# high_vix_rebound_long_1000

Campaign: `es_cboe_vix_level_state_intraday`

Mechanic: At 10:00 ET, buy ES when the latest prior Cboe VIX close rank is in the upper tail; flatten by 15:55.

Feature timing: `data/external/es_cboe_vix_level_features_20110103_20260609.csv` uses the latest Cboe VIX close strictly before the ES session date. Signals are evaluated on a completed 1-minute bar and entered by the engine on the next bar.

Entry module: `cboe_vix_level_state`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

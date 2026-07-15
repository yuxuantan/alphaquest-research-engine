# falling_vxn_vix_ratio_long_1200

Campaign: `es_cboe_vxn_vix_dispersion_intraday`

Mechanic: At 12:00 ET, buy ES when the latest prior 1-day change in the Cboe VXN/VIX ratio ranks in the lower tail; flatten by 15:55.

Feature timing: `data/external/es_cboe_vxn_vix_dispersion_features_20110103_20260609.csv` uses the latest Cboe VIX and VXN closes strictly before the ES session date. Signals are evaluated on a completed 1-minute bar and entered by the engine on the next bar.

Entry module: `cboe_vxn_vix_dispersion`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

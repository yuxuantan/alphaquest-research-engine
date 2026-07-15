# low_vxn_vix_ratio_long_1130

Campaign: `es_cboe_vxn_vix_dispersion_intraday`

Mechanic: At 11:30 ET, buy ES when the latest prior Cboe VXN/VIX ratio rank is in the lower tail; flatten by 15:55.

Feature timing: `data/external/es_cboe_vxn_vix_dispersion_features_20110103_20260609.csv` uses the latest Cboe VIX and VXN closes strictly before the ES session date. Signals are evaluated on a completed 1-minute bar and entered by the engine on the next bar.

Entry module: `cboe_vxn_vix_dispersion`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_cboe_vxn_vix_dispersion_intraday/low_vxn_vix_ratio_long_1130/rescue1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.

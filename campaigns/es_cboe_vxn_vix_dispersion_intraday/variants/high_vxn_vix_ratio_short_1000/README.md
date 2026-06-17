# high_vxn_vix_ratio_short_1000

Campaign: `es_cboe_vxn_vix_dispersion_intraday`

Mechanic: At 10:00 ET, short ES when the latest prior Cboe VXN/VIX ratio rank is in the upper tail; flatten by 15:55.

Feature timing: `data/external/es_cboe_vxn_vix_dispersion_features_20110103_20260609.csv` uses the latest Cboe VIX and VXN closes strictly before the ES session date. Signals are evaluated on a completed 1-minute bar and entered by the engine on the next bar.

Entry module: `cboe_vxn_vix_dispersion`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

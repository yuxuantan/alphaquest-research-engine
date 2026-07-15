# low_vix_complacency_short_1030

Campaign: `es_cboe_vix_level_state_intraday`

Mechanic: At 10:30 ET, short ES when the latest prior Cboe VIX close rank is in the lower tail; flatten by 15:55.

Feature timing: `data/external/es_cboe_vix_level_features_20110103_20260609.csv` uses the latest Cboe VIX close strictly before the ES session date. Signals are evaluated on a completed 1-minute bar and entered by the engine on the next bar.

Entry module: `cboe_vix_level_state`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

## Rescue Attempt 1
Original low-VIX complacency short failed core with 0/27 profitable combinations; rescue preserves the same low-VIX short mechanic and tests a stricter lower-tail rank neighborhood with the adjacent low-R stop/target space.

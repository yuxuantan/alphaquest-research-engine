# vix_crush_rebound_long_1200

Campaign: `es_cboe_vix_level_state_intraday`

Mechanic: At 12:00 ET, buy ES when the latest prior one-day VIX change rank is in the lower tail; flatten by 15:55.

Feature timing: `data/external/es_cboe_vix_level_features_20110103_20260609.csv` uses the latest Cboe VIX close strictly before the ES session date. Signals are evaluated on a completed 1-minute bar and entered by the engine on the next bar.

Entry module: `cboe_vix_level_state`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

## Rescue Attempt 1
Original VIX-crush rebound long failed core with 0/27 profitable combinations; rescue preserves the same one-day VIX drop long mechanic and tests the adjacent lower-tail rank and wider-stop space around the least-bad rows.

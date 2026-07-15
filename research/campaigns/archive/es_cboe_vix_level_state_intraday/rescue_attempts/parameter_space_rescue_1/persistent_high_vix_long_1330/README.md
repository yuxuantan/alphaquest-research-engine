# persistent_high_vix_long_1330

Campaign: `es_cboe_vix_level_state_intraday`

Mechanic: At 13:30 ET, buy ES when the latest prior 5-session VIX mean rank is in the upper tail; flatten by 15:55.

Feature timing: `data/external/es_cboe_vix_level_features_20110103_20260609.csv` uses the latest Cboe VIX close strictly before the ES session date. Signals are evaluated on a completed 1-minute bar and entered by the engine on the next bar.

Entry module: `cboe_vix_level_state`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

## Rescue Attempt 1
Original persistent high-VIX long failed core with 0/27 profitable combinations; rescue preserves the same 5-session VIX mean high-state long mechanic and tests the adjacent rank neighborhood with wide-stop/high-R exits.

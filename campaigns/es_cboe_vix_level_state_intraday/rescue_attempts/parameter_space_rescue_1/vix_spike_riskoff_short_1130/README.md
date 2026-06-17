# vix_spike_riskoff_short_1130

Campaign: `es_cboe_vix_level_state_intraday`

Mechanic: At 11:30 ET, short ES when the latest prior one-day VIX change rank is in the upper tail; flatten by 15:55.

Feature timing: `data/external/es_cboe_vix_level_features_20110103_20260609.csv` uses the latest Cboe VIX close strictly before the ES session date. Signals are evaluated on a completed 1-minute bar and entered by the engine on the next bar.

Entry module: `cboe_vix_level_state`.
Stop module: `percent_from_entry`.
Target module: `fixed_r`.

## Rescue Attempt 1
Original VIX-spike risk-off short failed core with 4/27 profitable combinations; rescue preserves the same one-day VIX spike short mechanic and tests the adjacent wide-stop/moderate-R neighborhood around the least-bad original rows.

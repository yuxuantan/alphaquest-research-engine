# eu_open_prior_down_long_0230

Campaign: `es_overnight_drift_european_open`

Edge expression: Enter long after the completed 02:25-02:30 ET ETH bar on prior-RTH-down sessions and hold through the second half of the European-open transfer window, flattening by 03:30 ET.

Why it should be profitable: If the drift is not confined to the first print after 02:00 ET, the 02:30-03:30 ET variant should capture follow-through as European futures and cash-market participants complete the same risk-transfer process.

Data and timing: uses local ES ETH/RTH Databento OHLCV, completed 5-minute ETH bars, next-bar entry, one-tick slippage, commissions, pessimistic same-bar TP/SL handling, and a configured ETH cutoff at 03:30:00.

Parameter grid: 27 combinations. Entry tunables: entry.params.min_prior_rth_down_ticks. Stop tunable: `sl.params.stop_pct`. Target tunable: `tp.params.target_r_multiple`.

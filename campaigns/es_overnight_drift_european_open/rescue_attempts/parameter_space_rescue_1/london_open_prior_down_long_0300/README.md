# london_open_prior_down_long_0300

Campaign: `es_overnight_drift_european_open`

Edge expression: Enter long after the completed 02:55-03:00 ET ETH bar on prior-RTH-down sessions and hold through 04:00 ET, testing whether the documented European-open drift extends into the London/cash-market handoff.

Why it should be profitable: A later window is plausible only if the same overnight imbalance is still being transferred as European cash liquidity opens; the prior-RTH-down filter keeps it tied to the paper's imbalance mechanism rather than generic overnight seasonality.

Data and timing: uses local ES ETH/RTH Databento OHLCV, completed 5-minute ETH bars, next-bar entry, one-tick slippage, commissions, pessimistic same-bar TP/SL handling, and a configured ETH cutoff at 04:00:00.

Parameter grid: 27 combinations. Entry tunables: entry.params.min_prior_rth_down_ticks. Stop tunable: `sl.params.stop_pct`. Target tunable: `tp.params.target_r_multiple`.


## Rescue Attempt 1

Original London-open variant had zero profitable combinations but its best-ranked run used the highest tested target. Rescue keeps the same 03:00 ET prior-down mechanic and tests only a wider stop/target geometry, with no target below 1.25R.

This rescue preserves the original modules, signal clock, data window, timeframe, and flatten rule. It changes only the fixed parameters and declared parameter space inside the same mechanics. All target R multiples are >= 1.0.

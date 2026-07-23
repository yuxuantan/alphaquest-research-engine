# eu_open_prior_down_long_0200

Campaign: `es_overnight_drift_european_open`

Edge expression: Enter long after the completed 01:55-02:00 ET ETH bar only when the prior completed RTH session closed down by the declared tick threshold, then flatten by 03:00 ET.

Why it should be profitable: The source links the overnight drift to order imbalances after prior U.S. trading. Conditioning on a prior RTH selloff should isolate sessions where European-open investors absorb or rebalance prior U.S. risk-off pressure.

Data and timing: uses local ES ETH/RTH Databento OHLCV, completed 5-minute ETH bars, next-bar entry, one-tick slippage, commissions, pessimistic same-bar TP/SL handling, and a configured ETH cutoff at 03:00:00.

Parameter grid: 27 combinations. Entry tunables: entry.params.min_prior_rth_down_ticks. Stop tunable: `sl.params.stop_pct`. Target tunable: `tp.params.target_r_multiple`.


## Rescue Attempt 1

Original grid had zero profitable combinations but enough trade density at the prior-down filter. Rescue keeps the same prior-RTH-down mechanic and tests only a wider stop ladder plus no sub-1R target choices.

This rescue preserves the original modules, signal clock, data window, timeframe, and flatten rule. It changes only the fixed parameters and declared parameter space inside the same mechanics. All target R multiples are >= 1.0.

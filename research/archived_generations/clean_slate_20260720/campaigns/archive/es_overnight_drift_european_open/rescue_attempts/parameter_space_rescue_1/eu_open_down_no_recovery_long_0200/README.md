# eu_open_down_no_recovery_long_0200

Campaign: `es_overnight_drift_european_open`

Edge expression: Enter long after the completed 01:55-02:00 ET ETH bar when the prior RTH session sold off and the ETH session has not already recovered more than the declared pre-signal return threshold.

Why it should be profitable: This version expresses the imbalance-transfer mechanism most tightly: prior U.S. selling creates potential overnight demand, but the signal is skipped if the evening ETH session already recovered too much before the European-open window.

Data and timing: uses local ES ETH/RTH Databento OHLCV, completed 5-minute ETH bars, next-bar entry, one-tick slippage, commissions, pessimistic same-bar TP/SL handling, and a configured ETH cutoff at 03:00:00.

Parameter grid: 81 combinations. Entry tunables: entry.params.min_prior_rth_down_ticks, entry.params.max_pre_signal_return_ticks. Stop tunable: `sl.params.stop_pct`. Target tunable: `tp.params.target_r_multiple`.


## Rescue Attempt 1

Original grid had zero profitable combinations and the strictest no-recovery settings reduced trade density. Rescue preserves the same prior-selloff/no-recovery filters but shifts the declared thresholds toward the denser part of the same mechanic and uses only 1.0R-or-higher targets.

This rescue preserves the original modules, signal clock, data window, timeframe, and flatten rule. It changes only the fixed parameters and declared parameter space inside the same mechanics. All target R multiples are >= 1.0.

# eu_open_unconditional_long_0200

Campaign: `es_overnight_drift_european_open`

Edge expression: Enter long after the completed 01:55-02:00 ET ETH bar and flatten by 03:00 ET, directly testing the positive 02:00-03:00 ET overnight drift window without a prior-day filter.

Why it should be profitable: If the paper's concentrated European-open drift persists, a simple long exposure in the exact 02:00-03:00 ET window should earn enough average movement to overcome one-tick slippage and commissions without needing ex-post filters.

Data and timing: uses local ES ETH/RTH Databento OHLCV, completed 5-minute ETH bars, next-bar entry, one-tick slippage, commissions, pessimistic same-bar TP/SL handling, and a configured ETH cutoff at 03:00:00.

Parameter grid: 9 combinations. Entry tunables: none. Stop tunable: `sl.params.stop_pct`. Target tunable: `tp.params.target_r_multiple`.

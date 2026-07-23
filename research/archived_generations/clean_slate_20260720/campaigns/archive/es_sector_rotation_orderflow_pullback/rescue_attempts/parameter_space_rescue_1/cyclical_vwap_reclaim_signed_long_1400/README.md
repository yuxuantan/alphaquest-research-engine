# cyclical_vwap_reclaim_signed_long_1400

Long ES only when lagged cyclical-minus-defensive sector leadership is in the upper tail, then wait for a completed VWAP pullback/reclaim through 14:00 ET with same-bar signed-volume confirmation. This variant uses a broader risk-on sector state and broader aggregate orderflow rather than larger-trade buckets.


## parameter_space_rescue_1

All original variants failed before WFA. This one allowed rescue keeps the entry mechanic, entry parameter grid, TP module/grid, data, costs, fills, sessions, and validation gates unchanged. It only widens the stop-loss parameter space to `[0.0025, 0.004, 0.006]` and sets the fixed stop default to `0.004`.

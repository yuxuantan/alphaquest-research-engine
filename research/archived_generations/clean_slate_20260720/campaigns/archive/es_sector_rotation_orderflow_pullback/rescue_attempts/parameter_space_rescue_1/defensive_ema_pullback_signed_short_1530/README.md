# defensive_ema_pullback_signed_short_1530

Short ES only when lagged one-day cyclical-minus-defensive sector leadership is in the lower tail, then require a completed EMA pullback continuation with negative signed-volume confirmation. This broadens the short-side window while keeping the same sector-state plus orderflow-pullback edge.


## parameter_space_rescue_1

All original variants failed before WFA. This one allowed rescue keeps the entry mechanic, entry parameter grid, TP module/grid, data, costs, fills, sessions, and validation gates unchanged. It only widens the stop-loss parameter space to `[0.0025, 0.004, 0.006]` and sets the fixed stop default to `0.004`.

# financial_industrial_ema_pullback_large10_long_1500

Long ES only when lagged financial/industrial leadership versus SPY is in the upper tail, then require a completed EMA pullback continuation with aligned large-10 aggregate orderflow through 15:00 ET. The thesis is that economically sensitive sector leadership should favor buyable intraday pullbacks.


## parameter_space_rescue_1

All original variants failed before WFA. This one allowed rescue keeps the entry mechanic, entry parameter grid, TP module/grid, data, costs, fills, sessions, and validation gates unchanged. It only widens the stop-loss parameter space to `[0.0025, 0.004, 0.006]` and sets the fixed stop default to `0.004`.

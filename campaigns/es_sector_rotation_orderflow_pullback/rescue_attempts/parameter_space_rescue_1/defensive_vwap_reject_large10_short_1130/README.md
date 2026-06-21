# defensive_vwap_reject_large10_short_1130

Short ES only when lagged cyclical-minus-defensive leadership is in the lower tail, then wait for a completed VWAP-side rejection with aligned large-10 sell flow during the morning. This tests whether defensive rotation turns VWAP pullbacks into continuation shorts rather than dip buys.


## parameter_space_rescue_1

All original variants failed before WFA. This one allowed rescue keeps the entry mechanic, entry parameter grid, TP module/grid, data, costs, fills, sessions, and validation gates unchanged. It only widens the stop-loss parameter space to `[0.0025, 0.004, 0.006]` and sets the fixed stop default to `0.004`.

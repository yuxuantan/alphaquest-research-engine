# growth_vwap_reclaim_large10_long_1130

Long ES only when lagged growth-minus-defensive sector leadership is in the upper tail, then wait for a completed VWAP pullback/reclaim between 10:00 and 11:30 ET with aligned large-10 aggregate orderflow. This is intended to test whether risk-on sector rotation improves the quality of morning VWAP continuation entries.


## parameter_space_rescue_1

All original variants failed before WFA. This one allowed rescue keeps the entry mechanic, entry parameter grid, TP module/grid, data, costs, fills, sessions, and validation gates unchanged. It only widens the stop-loss parameter space to `[0.0025, 0.004, 0.006]` and sets the fixed stop default to `0.004`.

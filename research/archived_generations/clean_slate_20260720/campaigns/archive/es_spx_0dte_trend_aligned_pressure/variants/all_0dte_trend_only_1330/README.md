# all_0dte_trend_only_1330

Campaign: `es_spx_0dte_trend_aligned_pressure`

Mechanic: On all locally known SPX 0DTE sessions from the 2016 M/W/F Weeklys era onward, excluding standard monthly OPEX, wait for the completed 13:29 ET ES bar. If the latest completed 30-minute and 120-minute windows both show higher highs and higher lows than their prior windows, enter long. If both show lower highs and lower lows, enter short.

Entry module: `spx_0dte_trend_aligned_pressure`. The module uses the local SPX 0DTE calendar and completed ES 1-minute bars only. The signal uses the completed close at 13:30 ET and relies on the engine for next-bar execution.

Stop module: `percent_from_entry` with declared stop grid.

Target module: `fixed_r` with declared R-multiple grid.

Parameter grid: `sl.params.stop_pct` x `tp.params.target_r_multiple` = 9 combinations.

Lookahead controls: no option-flow totals, strike pinning, final VWAP, future high/low, post-signal trend state, or post-entry data is used.

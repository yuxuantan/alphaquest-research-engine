# mwf_two_sided_fade_1030

Campaign: `es_spx_0dte_expiration_pressure`

Mechanic: On Monday/Wednesday/Friday SPX 0DTE sessions, excluding standard monthly OPEX Fridays, fade the completed 10:30 ET open-to-signal move. This expresses the same 0DTE pinning/liquidity-provision mechanism on the legacy expiry weekdays.

Entry module: `spx_0dte_expiration_pressure`. The module reads the precomputed local calendar `data/external/spx_0dte_calendar_sessions_20110103_20260609.csv`, excludes standard monthly/quarterly OPEX Fridays by default, waits for the configured completed 1-minute bar close, and relies on the engine for next-bar execution.

Stop module: `percent_from_entry` with declared stop grid.

Target module: `fixed_r` with declared R-multiple grid.

Parameter grid: `entry.params.min_abs_move_ticks` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 27 combinations.

Lookahead controls: no option flow, strike pin, same-day option volume, final VWAP, future high/low, or post-entry data is used.

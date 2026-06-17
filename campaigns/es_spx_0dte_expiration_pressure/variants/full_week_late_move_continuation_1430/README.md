# full_week_late_move_continuation_1430

Campaign: `es_spx_0dte_expiration_pressure`

Mechanic: During the post-May-2022 full-week SPX 0DTE regime, follow a large completed 14:30 ET open-to-signal move into the late session. This tests the opposite expression of the same edge: gamma-hedging feedback amplifies large same-day moves near expiry.

Entry module: `spx_0dte_expiration_pressure`. The module reads the precomputed local calendar `data/external/spx_0dte_calendar_sessions_20110103_20260609.csv`, excludes standard monthly/quarterly OPEX Fridays by default, waits for the configured completed 1-minute bar close, and relies on the engine for next-bar execution.

Stop module: `percent_from_entry` with declared stop grid.

Target module: `fixed_r` with declared R-multiple grid.

Parameter grid: `entry.params.min_abs_move_ticks` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 27 combinations.

Lookahead controls: no option flow, strike pin, same-day option volume, final VWAP, future high/low, or post-entry data is used.

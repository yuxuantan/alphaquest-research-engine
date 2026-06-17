# full_week_up_move_fade_short_1000 Rescue 1

Campaign: `es_spx_0dte_expiration_pressure`

Scope: one allowed rescue for failed original `full_week_up_move_fade_short_1000`.

Allowed changes used: `entry.params.min_abs_move_ticks`, `sl.params.stop_pct`, and `tp.params.target_r_multiple` parameter/default spaces only.

Rationale: Tests a tighter short-side stop neighborhood and nearby upside-extension thresholds; the full-week 0DTE short fade mechanic is unchanged.

Retained: entry module, calendar bucket, trigger mode, direction, signal time, data window, costs, fill assumptions, stage gates, stop module, and target module.

Grid: {'entry.params.min_abs_move_ticks': [4, 8, 12], 'sl.params.stop_pct': [0.001, 0.0015, 0.002], 'tp.params.target_r_multiple': [1.5, 2.0, 2.5]}

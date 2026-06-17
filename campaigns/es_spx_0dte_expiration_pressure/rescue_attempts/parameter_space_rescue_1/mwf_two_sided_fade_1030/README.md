# mwf_two_sided_fade_1030 Rescue 1

Campaign: `es_spx_0dte_expiration_pressure`

Scope: one allowed rescue for failed original `mwf_two_sided_fade_1030`.

Allowed changes used: `entry.params.min_abs_move_ticks`, `sl.params.stop_pct`, and `tp.params.target_r_multiple` parameter/default spaces only.

Rationale: Centers the legacy M/W/F two-sided fade around the strongest original threshold and higher R exits without changing the calendar bucket or direction logic.

Retained: entry module, calendar bucket, trigger mode, direction, signal time, data window, costs, fill assumptions, stage gates, stop module, and target module.

Grid: {'entry.params.min_abs_move_ticks': [20, 24, 28], 'sl.params.stop_pct': [0.0015, 0.0025, 0.004], 'tp.params.target_r_multiple': [1.5, 2.0, 2.5]}

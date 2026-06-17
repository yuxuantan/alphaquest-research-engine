# full_week_late_move_continuation_1430 Rescue 1

Campaign: `es_spx_0dte_expiration_pressure`

Scope: one allowed rescue for failed original `full_week_late_move_continuation_1430`.

Allowed changes used: `entry.params.min_abs_move_ticks`, `sl.params.stop_pct`, and `tp.params.target_r_multiple` parameter/default spaces only.

Rationale: Centers the late continuation test on stricter but still dense move thresholds and wider stops/targets; the 14:30 full-week continuation mechanic is unchanged.

Retained: entry module, calendar bucket, trigger mode, direction, signal time, data window, costs, fill assumptions, stage gates, stop module, and target module.

Grid: {'entry.params.min_abs_move_ticks': [80, 96, 112], 'sl.params.stop_pct': [0.003, 0.004, 0.005], 'tp.params.target_r_multiple': [1.5, 2.0, 2.5]}

# full_week_down_move_fade_long_1000 Rescue 1

Campaign: `es_spx_0dte_expiration_pressure`

Scope: one allowed rescue for failed original `full_week_down_move_fade_long_1000`.

Allowed changes used: `entry.params.min_abs_move_ticks`, `sl.params.stop_pct`, and `tp.params.target_r_multiple` parameter/default spaces only.

Rationale: Lower early-downside extension thresholds and wider stops/targets around the positive original long-fade pocket while preserving full-week 0DTE long fade mechanics.

Retained: entry module, calendar bucket, trigger mode, direction, signal time, data window, costs, fill assumptions, stage gates, stop module, and target module.

Grid: {'entry.params.min_abs_move_ticks': [2, 4, 8], 'sl.params.stop_pct': [0.003, 0.004, 0.005], 'tp.params.target_r_multiple': [1.5, 2.0, 2.5]}

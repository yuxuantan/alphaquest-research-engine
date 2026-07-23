# tue_thu_two_sided_fade_1030 Rescue 1

Campaign: `es_spx_0dte_expiration_pressure`

Scope: one allowed rescue for failed original `tue_thu_two_sided_fade_1030`.

Allowed changes used: `entry.params.min_abs_move_ticks`, `sl.params.stop_pct`, and `tp.params.target_r_multiple` parameter/default spaces only.

Rationale: Tests stricter Tuesday/Thursday move-extension thresholds after the original broad fade failed; the two-sided new-expiry weekday fade mechanic is unchanged.

Retained: entry module, calendar bucket, trigger mode, direction, signal time, data window, costs, fill assumptions, stage gates, stop module, and target module.

Grid: {'entry.params.min_abs_move_ticks': [32, 40, 48], 'sl.params.stop_pct': [0.0015, 0.0025, 0.004], 'tp.params.target_r_multiple': [1.0, 1.5, 2.0]}

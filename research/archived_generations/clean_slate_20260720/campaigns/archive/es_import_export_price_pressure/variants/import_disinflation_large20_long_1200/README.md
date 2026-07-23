# import_disinflation_large20_long_1200

Long ES at noon when lagged 3-month import-price inflation is in its lower 45% and completed morning price action is positive with non-negative cumulative large-20-lot signed flow.

Why this should be profitable before testing: A benign import-price state should be most tradable when larger ES trades agree with price strength, because larger aggressive participation is less likely to be noise than one or two early bars.

Time/session rationale: Noon gives the cash session enough time to reveal institutional participation while retaining several hours before the configured flatten cutoff.

Pre-PnL density at fixed review settings: 851 full-sample signals, 55.15/year; limited-core reference 97.14/year; WFA90 54.01/year; latest year 66.05/year.

Parameter grid declared before testing: `entry.params.min_session_return_bps` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 27 combinations. `target_r_multiple` is never below 1.0R. The macro rank threshold, entry time, flow column, data, costs, sessions, and flatten rules are fixed before testing.

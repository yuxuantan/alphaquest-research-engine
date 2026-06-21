# import_disinflation_signed_long_1030

Long ES at 10:30 ET when lagged 3-month import-price inflation is in its lower 45% of the 120-month history and the completed 10:29 bar shows ES trading at or above the RTH open with non-negative cumulative signed flow.

Why this should be profitable before testing: Low import-price inflation reduces input-cost and inflation-risk pressure. If ES has already confirmed with completed price strength and non-negative aggregate flow, the session should be more likely to continue upward than an unfiltered 10:30 strength trade.

Time/session rationale: 10:30 ET is after the noisy open but early enough to capture same-day repricing if a benign import-price regime supports risk-on continuation.

Pre-PnL density at fixed review settings: 823 full-sample signals, 53.34/year; limited-core reference 90.66/year; WFA90 52.64/year; latest year 66.05/year.

Parameter grid declared before testing: `entry.params.min_session_return_bps` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 27 combinations. `target_r_multiple` is never below 1.0R. The macro rank threshold, entry time, flow column, data, costs, sessions, and flatten rules are fixed before testing.

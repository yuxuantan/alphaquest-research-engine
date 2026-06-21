# import_disinflation_large20_long_1430

Long ES at 14:30 ET when lagged import-price inflation is in its lower 45% and the completed session remains above the RTH open with non-negative cumulative large-20-lot flow.

Why this should be profitable before testing: If import-price disinflation supports risk appetite, late-session long continuation should be more credible when large-trade flow has not contradicted the price rise.

Time/session rationale: 14:30 ET tests whether the same macro/orderflow state persists into the late-day risk-allocation window while still leaving time for a same-day target or stop before flatten.

Pre-PnL density at fixed review settings: 842 full-sample signals, 54.57/year; limited-core reference 95.85/year; WFA90 53.94/year; latest year 62.04/year.

Parameter grid declared before testing: `entry.params.min_session_return_bps` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 27 combinations. `target_r_multiple` is never below 1.0R. The macro rank threshold, entry time, flow column, data, costs, sessions, and flatten rules are fixed before testing.

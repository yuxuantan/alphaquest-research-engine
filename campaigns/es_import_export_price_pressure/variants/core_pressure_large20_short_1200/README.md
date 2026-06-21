# core_pressure_large20_short_1200

Short ES at noon when core-vs-headline import-price momentum is at or above its 40th percentile and completed ES price weakness is confirmed by non-positive cumulative large-20-lot signed flow.

Why this should be profitable before testing: If broader import-cost pressure weighs on equity risk appetite, a noon short should only be attempted when larger ES trades have not absorbed the weakness.

Time/session rationale: Noon balances trade frequency with a cleaner large-trade confirmation window; later large20 thresholds fall below the 50/year latest-year gate.

Pre-PnL density at fixed review settings: 835 full-sample signals, 54.11/year; limited-core reference 80.95/year; WFA90 53.15/year; latest year 57.04/year.

Parameter grid declared before testing: `entry.params.min_session_return_bps` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 27 combinations. `target_r_multiple` is never below 1.0R. The macro rank threshold, entry time, flow column, data, costs, sessions, and flatten rules are fixed before testing.

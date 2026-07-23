# core_pressure_signed_short_1100

Short ES at 11:00 ET when core-vs-headline import-price momentum is at or above its 45th percentile and ES has a completed negative session return with non-positive cumulative signed flow.

Why this should be profitable before testing: Core import-price pressure is a broad input-cost/inflation signal. If ES is already weak and signed aggregate flow is not supporting buyers, equity-index continuation lower is economically plausible.

Time/session rationale: 11:00 ET allows enough post-open price discovery for weakness to confirm but avoids waiting until any pressure has already exhausted.

Pre-PnL density at fixed review settings: 950 full-sample signals, 61.57/year; limited-core reference 90.02/year; WFA90 62.72/year; latest year 54.04/year.

Parameter grid declared before testing: `entry.params.min_session_return_bps` x `sl.params.stop_pct` x `tp.params.target_r_multiple` = 27 combinations. `target_r_multiple` is never below 1.0R. The macro rank threshold, entry time, flow column, data, costs, sessions, and flatten rules are fixed before testing.


## parameter_space_rescue_1

User-authorized per-failed-variant rescue created on 2026-06-20 after the original limited-core failure. Only stop distance changed: `sl.params.stop_pct` grid is `[0.004, 0.006, 0.008]`, with fixed default `0.006`. Entry logic, macro threshold, signal time, flow column, TP module/grid, target reward:risk floor, data, costs, fills, sessions, and validation gates are unchanged.

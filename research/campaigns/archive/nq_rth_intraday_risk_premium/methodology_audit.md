# NQ RTH Intraday Risk Premium Methodology Audit

Verdict: FAIL.

This campaign was authored before NQ PnL inspection as a direct transfer of the ES RTH intraday risk-premium family. It tested unconditional long NQ exposure from five fixed completed RTH bars with same-session flattening.

Duplicate-edge decision: not a duplicate of `nq_calendar_weekday_bias` because weekday mappings are not selected; every weekday is long. Not a duplicate of volatility-managed or macro-conditioned risk-premium campaigns because this edge has no conditioning variable.

Pre-PnL density passed: 5/5 fixed entry rows cleared the full-history, limited-core, and latest-window signal-count gates.

All five predeclared NQ RTH intraday risk-premium variants failed limited_core_grid_test. Across 5 fixed core combinations, 0 were profitable, 0 passed benchmark gates, and 0 had Apex rule violations. The least-negative fixed row was late_morning_1100_long with top net -510.00, PF 0.9884, and 371 trades, so no variant reached monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

No monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate report was run because every variant failed `limited_core_grid_test`.

Selecting the least-negative `late_morning_1100_long` row, changing stops, or moving signal time after this result would be post-result narrowing of a failed edge. No rescue attempt is authorized.

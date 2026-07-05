# NQ Midday Range Orderflow Breakout Methodology Audit

Verdict: FAIL.

Authored before NQ PnL inspection as a direct transfer of the ES midday range orderflow breakout edge. NQ range caps were scaled using signal-count density only, not PnL.

Pre-PnL density passed: 45/45 declared entry rows cleared full-history, limited-core, and latest-window gates.

All five predeclared NQ midday range orderflow breakout variants failed limited_core_grid_test. Across 270 official core combinations, 0 were profitable, 0 passed benchmark gates, and 0 had Apex rule violations. The least-negative top row was lunch_1130_1300_signed_breakout_1430 with top net -370.00, PF 0.9754, and 261 trades, so no variant reached monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

No monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate report was run because every variant failed `limited_core_grid_test`.

Selecting the least-negative row or changing range caps/stops after this result would be post-result narrowing of a failed edge. No rescue attempt is authorized.

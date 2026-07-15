# NQ Overnight Return Late-Day Momentum Methodology Audit

Verdict: FAIL.

The campaign passed the pre-PnL density screen: 27/27 declared entry rows cleared the full-history, limited-core, and latest-252 signal-count gates. PnL was then inspected only through the staged limited-core grid.

All five predeclared variants failed `limited_core_grid_test`. Across 162 official core combinations, 0 were profitable, 0 passed benchmark gates, and 0 had Apex rule violations. The least-negative top row was `negative_overnight_short_1530` with top net -535.00 and PF 0.9335, which is still a failed result.

No monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate report was run because the campaign failed at limited core. Selecting a less-negative row, dropping the losing side, or changing exits after this result would be post-result narrowing of a failed edge.

The signal uses only completed RTH bars: prior completed RTH close, current RTH open, the completed first RTH window, and when applicable the completed 15:00-15:30 ET penultimate window. No final session return, future last-half-hour return, final VWAP, future orderflow, or future high/low is used.

No rescue attempt is authorized after NQ density or staged results.

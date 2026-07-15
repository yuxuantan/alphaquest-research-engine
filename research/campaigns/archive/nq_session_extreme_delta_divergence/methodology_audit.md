# NQ Session-Extreme Cumulative-Delta Divergence Methodology Audit

Verdict: FAIL.

The campaign passed the pre-PnL density screen: 20/20 declared entry rows cleared the full-history, limited-core, and latest-252 signal-count gates. PnL was then inspected only through the staged limited-core grid.

All five predeclared variants failed limited_core_grid_test. Across 60 official core combinations, only 1 was profitable, 0 passed benchmark gates, and 0 had Apex rule violations. The only positive-net row was `afternoon_high_delta_divergence_short` with top net 150.0 and PF 1.0215, but it failed concentration controls and the variant profitable rate was 1/12, far below the 0.70 gate.

No monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate report was run because the campaign failed at limited core. Selecting only the one positive row or widening/changing exits after seeing this result would be post-result narrowing of a failed edge.

The signal uses only completed one-minute RTH bars: prior completed session high/low, the completed signal bar high/low/close, and completed-bar aggregate signed volume. No final session high/low, final VWAP, future orderflow, future return, or same-day post-signal information is used.

No rescue attempt is authorized after NQ density or staged results.

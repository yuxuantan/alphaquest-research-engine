# NQ Intraday Periodicity Persistence Methodology Audit

Verdict: FAIL.

This campaign tested exactly five NQ variants expressing one edge: prior-session same-clock half-hour return persistence. The source was the ES periodicity campaign, ported before any NQ PnL inspection. Rescue was disabled.

No-lookahead review: the feature CSV uses `shift(1)` within each slot, so the current slot return is excluded from every rolling mean. Each signal uses the completed one-minute bar ending at the configured slot entry time and enters at the next bar open. Each variant flattens at the predeclared slot boundary.

Pre-PnL gate: all 45 declared entry rows passed density and signal/entry-bar availability. See `research_artifacts/nq_intraday_periodicity_persistence_density_audit_20260630.md`.

Staged result: all five variants failed `limited_core_grid_test`. Across 270 official combinations, 0 were profitable, 0 passed benchmark gates, and 0 had Apex violations. The least-negative top row was `afternoon_1330_slot_persistence` with top net -2138.75, PF 0.8379, and 343 trades.

Scientific-integrity decision: no rescue was authorized and no variant reached monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting. The campaign is closed as failed.

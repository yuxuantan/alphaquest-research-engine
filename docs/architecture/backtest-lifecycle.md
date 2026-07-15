# Backtest Lifecycle

1. Author one economic hypothesis and complete a ledger-backed duplicate-edge review.
2. Predeclare exactly five materially different variants, parameter spaces, and the rescue policy.
3. Lock config and mechanics, then run fail-closed data-lineage preflight.
4. Execute a small deterministic mechanics-validation slice without changing fills or PnL logic.
5. Export bar evidence for bar strategies or canonical event transitions for event-replay strategies.
6. Resolve all automated validation errors and write a hash-bound manual `approved_for_testing` decision.
7. Execute limited core grid tests, rejecting failures before later stages.
8. Continue through monkey, WFA stitched OOS, Monte Carlo, and simulated incubation gates.
9. Freeze mechanics and open the locked acceptance holdout only after every earlier gate passes.
10. Update the ledger and emit `PASS`, `FAIL`, or `NEEDS MANUAL REVIEW`.
11. Treat a pass only as a candidate pending independent review and paper/live incubation.

The runner halts before performance testing when an opted-in governance-v2 validation gate is missing, stale, rejected, hash-mismatched, or lane-incompatible. It also halts after a failed performance stage unless explicitly invoked in diagnostic mode. Later-stage folders from older runs are not evidence for a newer run.

Every governance-v2 staged execution has an explicit authored attempt identity. An attempt has zero runs while pending and exactly one immutable run after execution. A second execution requires a new attempt and test-run ID; the runner and registry both reject one attempt resolving to multiple runs.

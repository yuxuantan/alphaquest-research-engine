# Backtest Lifecycle

1. Author one campaign thesis and predeclare variants and parameter spaces.
2. Run preflight against authored configs and declared data.
3. Execute limited core grid tests.
4. Reject failures or continue to random-entry monkey testing.
5. Select parameters inside each WFA training window and stitch unseen OOS windows.
6. Stress stitched OOS trades with monkey and Monte Carlo tests.
7. Run simulated incubation.
8. Freeze mechanics and open the locked acceptance holdout.
9. Emit `PASS`, `FAIL`, or `NEEDS MANUAL REVIEW`.
10. Treat a pass only as a candidate pending independent review and paper/live incubation.

The runner halts after a failed stage unless explicitly invoked in diagnostic mode. Later-stage folders from older runs are not evidence for a newer run.

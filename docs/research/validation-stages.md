# Validation Stages

| Stage | Purpose |
| --- | --- |
| Limited core grid | Reject unprofitable, sparse, unstable, or rule-violating combinations quickly |
| Limited monkey | Require separation from randomized entries |
| Walk-forward analysis | Select parameters only on training windows and stitch unseen OOS trades |
| WFA OOS monkey | Stress the stitched OOS path against random entries |
| WFA OOS Monte Carlo | Estimate drawdown, concentration, and ruin distributions |
| Simulated incubation | Test a later untouched interval with frozen mechanics |
| Acceptance OOS | Open the locked final holdout only after the strategy is frozen |

Every stage is fail-closed. Missing data, malformed timestamps, ambiguous fills, incomplete summaries, or stale evidence produce failure or manual review rather than promotion.

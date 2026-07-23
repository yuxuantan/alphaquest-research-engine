# NQ Opening-Range Failed Breakout Orderflow Campaign Summary

Verdict: FAIL.

Rejected before staged NQ PnL: 2/29 declared entry-grid rows failed the pre-PnL density gate. The sparse rows were in or60_signed_failed_reclaim_1200 at min_reclaim_orderflow_imbalance=0.10 with max_reclaim_bars 3 and 4; latest-252-session signal counts were 24 and 25, and the 3-bar row also fell below 50 signals/year over full history. Dropping the strict 0.10 imbalance tier or the OR60 variant after this screen would be post-result narrowing of the declared five-variant edge. No NQ PnL was inspected.

Density summary:

| variant | rows | pass rows | min full/year | min limited/year | min latest-252 | verdict |
|---|---:|---:|---:|---:|---:|---|
| `or15_large10_failed_reclaim_1030` | 6 | 6 | 64.50 | 57.06 | 89 | PASS_DENSITY_ONLY |
| `or15_signed_failed_reclaim_1030` | 4 | 4 | 66.62 | 66.57 | 57 | PASS_DENSITY_ONLY |
| `or30_large20_failed_reclaim_1130` | 9 | 9 | 57.43 | 67.92 | 58 | PASS_DENSITY_ONLY |
| `or30_signed_failed_reclaim_1100` | 4 | 4 | 70.91 | 73.36 | 56 | PASS_DENSITY_ONLY |
| `or60_signed_failed_reclaim_1200` | 6 | 4 | 49.70 | 61.13 | 24 | FAIL |

Density audit: `research_artifacts/nq_opening_range_failed_breakout_orderflow_density_audit_20260630.md`.

No staged PnL, monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate report was run.

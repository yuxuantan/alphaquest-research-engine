# NQ prior-session flip retest orderflow density audit

Verdict: PASS.

No stop/target outcome, trade log, equity curve, staged PnL, WFA, Monte Carlo, simulated incubation, acceptance OOS, or holdout PnL was inspected for this audit.

- Rule: every declared entry-grid row must have at least 50 signals/year on full history and limited-core proxy, and at least 50 signals in the latest 252 sessions.
- Full window: 2011-01-03 through 2026-06-12, 3813 RTH sessions.
- Limited-core proxy window: 2011-02-22 through 2012-09-07, 371 RTH sessions.
- Latest window: last 252 RTH sessions ending 2026-06-12.
- Entry rows passing all windows: 45/45.
- Variants passing all entry rows: 5/5.

| Variant | Entry rows | Passing rows | Min full / year | Min limited-core / year | Min latest252 signals | Verdict |
|---|---:|---:|---:|---:|---:|---|
| `afternoon_large10_aligned_two_sided_flip` | 9 | 9 | 73.10 | 80.83 | 61 | PASS |
| `late_morning_large10_absorbed_two_sided_flip` | 9 | 9 | 87.30 | 88.30 | 74 | PASS |
| `midday_signed_aligned_two_sided_flip` | 9 | 9 | 95.10 | 93.74 | 84 | PASS |
| `morning_signed_absorbed_two_sided_flip` | 9 | 9 | 72.37 | 75.40 | 56 | PASS |
| `morning_signed_aligned_two_sided_flip` | 9 | 9 | 86.71 | 86.26 | 81 | PASS |

CSV detail: `research_artifacts/nq_prior_session_flip_retest_orderflow_density_audit_20260630.csv`
Summary CSV: `research_artifacts/nq_prior_session_flip_retest_orderflow_density_summary_20260630.csv`

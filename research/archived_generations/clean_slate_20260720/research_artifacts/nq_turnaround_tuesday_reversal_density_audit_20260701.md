# NQ Turnaround Tuesday Reversal Density Audit

Generated: 2026-07-01T03:05:00+08:00

Verdict before PnL: FAIL

Rows passing density: 0/45. Variants passing all density windows: 0/5.

Criteria: full-history and limited-core proxy windows require at least 40 eligible signals per year; latest-252-session window requires at least 40 eligible signals. No PnL was inspected.

| Variant | Rows Passing | Min Full/Year | Min Limited/Year | Min Latest-252 | Verdict |
|---|---:|---:|---:|---:|---|
| `tuesday_prior_gain_short_1000` | 0/9 | 12.69 | 11.55 | 17 | FAIL |
| `tuesday_prior_loss_long_1000` | 0/9 | 8.79 | 12.23 | 2 | FAIL |
| `tuesday_prior_loss_long_1130` | 0/9 | 8.79 | 12.23 | 2 | FAIL |
| `tuesday_two_day_loss_long_1030` | 0/9 | 11.24 | 13.58 | 6 | FAIL |
| `tuesday_vol_norm_loss_long_1200` | 0/9 | 9.78 | 10.19 | 7 | FAIL |

The campaign was rejected before staged PnL. Dropping sparse Tuesday variants or loosening thresholds after this audit would be post-result narrowing.

Detail CSV: `research_artifacts/nq_turnaround_tuesday_reversal_density_audit_20260701.csv`
Summary CSV: `research_artifacts/nq_turnaround_tuesday_reversal_density_summary_20260701.csv`

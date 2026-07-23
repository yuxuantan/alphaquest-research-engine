# nq_ema_pullback_orderflow_continuation density audit

Decision: PASS

Full subset: 2011-01-03 through 2026-06-12 (15.44 calendar years).
Limited-core proxy subset: 2011-02-22 through 2012-09-07 (1.54 calendar years), resolved from the staged runner random_fraction window.
Latest-session window: 2025-06-09 through 2026-06-12 (252 sessions).

Gate: every declared entry-grid row must have at least 50 signals/year on full history, at least 50 signals/year on the limited-core proxy window, and at least 50 raw signals in the latest 252 sessions. No PnL was inspected.

| variant_id | entry_rows | rows_passing | min_full_per_year | min_limited_per_year | min_latest252 | pass |
|---|---:|---:|---:|---:|---:|---|
| `afternoon_large10_two_sided_ema_pullback_1430` | 9 | 9 | 213.52 | 190.40 | 236 | PASS |
| `late_morning_signed_long_ema_pullback_1200` | 9 | 9 | 131.46 | 125.64 | 132 | PASS |
| `late_morning_signed_short_ema_pullback_1200` | 9 | 9 | 113.53 | 106.86 | 109 | PASS |
| `late_morning_signed_two_sided_ema_pullback_1130` | 9 | 9 | 185.09 | 178.09 | 191 | PASS |
| `lunch_signed_two_sided_ema_pullback_1300` | 9 | 9 | 213.13 | 197.52 | 226 | PASS |

Detail CSV: `research_artifacts/nq_ema_pullback_orderflow_continuation_density_audit_20260630.csv`
Summary CSV: `research_artifacts/nq_ema_pullback_orderflow_continuation_density_summary_20260630.csv`

# nq_key_reversal_orderflow_reversal density audit

Decision: FAIL

Full subset: 2011-01-03 through 2026-06-12 (15.44 calendar years).
Limited-core proxy subset: 2011-02-22 through 2012-09-07 (1.54 calendar years), resolved from the staged runner random_fraction window.
Latest-session window: 2025-06-09 through 2026-06-12 (252 sessions).

Gate: every declared entry-grid row must have at least 50 signals/year on full history, at least 50 signals/year on the limited-core proxy window, and at least 50 raw signals in the latest 252 sessions. No PnL was inspected.

| variant_id | entry_rows | rows_passing | min_full_per_year | min_limited_per_year | min_latest252 | pass |
|---|---:|---:|---:|---:|---:|---|
| `afternoon_large20_two_sided_key_reversal_1530` | 6 | 3 | 93.32 | 22.02 | 163 | FAIL |
| `late_morning_large10_down_sweep_reclaim_long_1230` | 6 | 3 | 141.96 | 37.56 | 236 | FAIL |
| `late_morning_large10_up_sweep_reject_short_1230` | 6 | 3 | 139.49 | 40.15 | 235 | FAIL |
| `midday_signed_two_sided_key_reversal_1400` | 6 | 3 | 134.96 | 18.78 | 248 | FAIL |
| `morning_signed_two_sided_key_reversal_1130` | 6 | 4 | 164.88 | 47.92 | 252 | FAIL |

Detail CSV: `research_artifacts/nq_key_reversal_orderflow_reversal_density_audit_20260630.csv`
Summary CSV: `research_artifacts/nq_key_reversal_orderflow_reversal_density_summary_20260630.csv`

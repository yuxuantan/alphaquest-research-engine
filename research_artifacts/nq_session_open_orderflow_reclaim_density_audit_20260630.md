# nq_session_open_orderflow_reclaim density audit

Decision: FAIL

Full subset: 2011-01-03 through 2026-06-12 (15.44 calendar years).
Limited-core proxy subset: 2011-02-22 through 2012-09-07 (1.54 calendar years), resolved from the staged runner random_fraction window.
Latest-session window: 2025-06-09 through 2026-06-12 (252 sessions).

Gate: every declared entry-grid row must have at least 50 signals/year on full history, at least 50 signals/year on the limited-core proxy window, and at least 50 raw signals in the latest 252 sessions. No PnL was inspected.

| variant_id | entry_rows | rows_passing | min_full_per_year | min_limited_per_year | min_latest252 | pass |
|---|---:|---:|---:|---:|---:|---|
| `afternoon_large20_down_open_reclaim_long` | 9 | 9 | 102.78 | 60.23 | 133 | PASS |
| `afternoon_large20_up_open_reject_short` | 9 | 6 | 86.78 | 45.98 | 112 | FAIL |
| `midday_large10_two_sided_open_reclaim` | 9 | 9 | 161.19 | 96.49 | 214 | PASS |
| `morning_down_open_reclaim_long` | 9 | 6 | 116.57 | 44.68 | 175 | FAIL |
| `morning_up_open_reject_short` | 9 | 6 | 110.42 | 39.50 | 171 | FAIL |

Detail CSV: `research_artifacts/nq_session_open_orderflow_reclaim_density_audit_20260630.csv`
Summary CSV: `research_artifacts/nq_session_open_orderflow_reclaim_density_summary_20260630.csv`

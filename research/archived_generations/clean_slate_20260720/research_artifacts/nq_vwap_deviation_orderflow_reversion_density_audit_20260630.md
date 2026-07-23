# nq_vwap_deviation_orderflow_reversion density audit

Decision: FAIL

Full subset: 2011-01-03 through 2026-06-12 (15.44 calendar years).
Limited-core proxy subset: 2011-02-22 through 2012-09-07 (1.54 calendar years), resolved from the staged runner random_fraction window.
Latest-session window: 2025-06-09 through 2026-06-12 (252 sessions).

Gate: every declared entry-grid row must have at least 50 signals/year on full history, at least 50 signals/year on the limited-core proxy window, and at least 50 raw signals in the latest 252 sessions. No PnL was inspected.

| variant_id | entry_rows | rows_passing | min_full_per_year | min_limited_per_year | min_latest252 | pass |
|---|---:|---:|---:|---:|---:|---|
| `afternoon_signed_counterflow_1530` | 9 | 9 | 175.76 | 85.48 | 248 | PASS |
| `midday_large20_counterflow_1400` | 9 | 9 | 159.05 | 68.00 | 240 | PASS |
| `midday_signed_counterflow_1400` | 9 | 9 | 169.35 | 62.17 | 248 | PASS |
| `morning_large10_counterflow_1200` | 9 | 6 | 147.85 | 33.68 | 248 | FAIL |
| `morning_signed_counterflow_1200` | 9 | 6 | 142.80 | 29.79 | 235 | FAIL |

Detail CSV: `research_artifacts/nq_vwap_deviation_orderflow_reversion_density_audit_20260630.csv`
Summary CSV: `research_artifacts/nq_vwap_deviation_orderflow_reversion_density_summary_20260630.csv`

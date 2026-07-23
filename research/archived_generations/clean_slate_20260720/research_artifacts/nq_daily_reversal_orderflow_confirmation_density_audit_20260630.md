# nq_daily_reversal_orderflow_confirmation density audit

- Audit date: 2026-06-30
- Full window: 2011-01-03 to 2026-06-12 (3813 sessions)
- Limited-core window: 2011-02-22 to 2012-09-07
- Latest-252 window: 2025-06-09 to 2026-06-12
- Declared entry rows: 45
- Density passes: 45
- Density failures: 0

Gate: each declared entry row must produce at least 50 signals/year in full history, at least 50 signals/year in the limited-core window, and at least 50 signals in the latest 252 sessions before any PnL is inspected.

| variant | rows | pass rows | min full/year | min limited/year | min latest-252 | verdict |
|---|---:|---:|---:|---:|---:|---|
| afternoon90_1d_flow_confirm_1400 | 9 | 9 | 81.48 | 102.50 | 80 | PASS |
| first120_3d_flow_confirm_1130 | 9 | 9 | 68.98 | 105.10 | 58 | PASS |
| first150_5d_flow_confirm_1200 | 9 | 9 | 63.41 | 96.02 | 58 | PASS |
| first60_1d_flow_confirm_1030 | 9 | 9 | 71.06 | 92.77 | 72 | PASS |
| first90_2d_flow_confirm_1100 | 9 | 9 | 70.15 | 97.31 | 63 | PASS |

Machine summary:

```json
{
  "all_rows_density_pass": true,
  "audit_date": "2026-06-30",
  "campaign_id": "nq_daily_reversal_orderflow_confirmation",
  "declared_entry_rows": 45,
  "density_fail_rows": 0,
  "density_pass_rows": 45,
  "failed_variants": [],
  "full_end_date": "2026-06-12",
  "full_sessions": 3813,
  "full_start_date": "2011-01-03",
  "latest_252_end_date": "2026-06-12",
  "latest_252_start_date": "2025-06-09",
  "limited_end_date": "2012-09-07",
  "limited_start_date": "2011-02-22",
  "min_full_signals_per_year": 63.41190813974109,
  "min_latest_252_signals": 58,
  "min_limited_signals_per_year": 92.77220248667851,
  "prepared_rows": 297414
}
```

Detail CSV: `research_artifacts/nq_daily_reversal_orderflow_confirmation_density_audit_20260630.csv`

Summary CSV: `research_artifacts/nq_daily_reversal_orderflow_confirmation_density_summary_20260630.csv`

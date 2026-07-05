# nq_overnight_range_compression_orderflow_breakout density audit

- Audit date: 2026-06-30
- Full window: 2011-01-03 to 2026-05-29 (3803 sessions)
- Limited-core window: 2011-02-22 to 2012-09-07
- Latest-252 window: 2025-05-23 to 2026-05-29
- Declared entry rows: 45
- Density passes: 45
- Density failures: 0

Gate: each declared entry row must produce at least 50 signals/year in full history, at least 50 signals/year in the limited-core window, and at least 50 signals in the latest 252 sessions before any PnL is inspected.

| variant | rows | pass rows | min full/year | min limited/year | min latest-252 | verdict |
|---|---:|---:|---:|---:|---:|---|
| afternoon_large20_two_sided_breakout_1500 | 9 | 9 | 66.17 | 72.01 | 66 | PASS |
| late_morning_large10_two_sided_breakout_1130 | 9 | 9 | 69.67 | 69.42 | 70 | PASS |
| midday_signed_two_sided_breakout_1300 | 9 | 9 | 69.35 | 73.96 | 67 | PASS |
| morning_large10_two_sided_breakout_1100 | 9 | 9 | 67.66 | 70.07 | 66 | PASS |
| morning_signed_two_sided_breakout_1030 | 9 | 9 | 63.05 | 67.47 | 62 | PASS |

Machine summary:

```json
{
  "all_rows_density_pass": true,
  "audit_date": "2026-06-30",
  "campaign_id": "nq_overnight_range_compression_orderflow_breakout",
  "declared_entry_rows": 45,
  "density_fail_rows": 0,
  "density_pass_rows": 45,
  "full_end_date": "2026-05-29",
  "full_sessions": 3803,
  "full_start_date": "2011-01-03",
  "latest_252_end_date": "2026-05-29",
  "latest_252_start_date": "2025-05-23",
  "limited_end_date": "2012-09-07",
  "limited_start_date": "2011-02-22",
  "min_full_signals_per_year": 63.05026666666667,
  "min_latest_252_signals": 62,
  "min_limited_signals_per_year": 67.47069271758437,
  "prepared_rows": 296634,
  "timeframe": "5m"
}
```

Detail CSV: `research_artifacts/nq_overnight_range_compression_orderflow_breakout_density_audit_20260630.csv`

Summary CSV: `research_artifacts/nq_overnight_range_compression_orderflow_breakout_density_summary_20260630.csv`

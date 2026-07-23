# nq_chartfanatics_smt_po3_midpoint_reversion density audit

- Audit date: 2026-06-30
- Full window: 2011-01-03 to 2026-06-09 (3807 sessions)
- Limited-core window: 2011-02-22 to 2012-09-06 (369 sessions)
- Latest-252 window: 2025-06-04 to 2026-06-09
- Declared entry rows: 45
- Density passes: 0
- Density failures: 45

Gate: each declared entry row must produce at least 50 signals/year in full history, at least 50 signals/year in the limited-core window, and at least 50 signals in the latest 252 sessions before any PnL is inspected.

| variant | rows | pass rows | min full/year | min limited/year | min latest-252 | verdict |
|---|---:|---:|---:|---:|---:|---|
| prior_high_smt_short_1000_1130 | 9 | 0 | 32.43 | 21.85 | 35 | FAIL |
| prior_high_smt_short_1030_1200 | 9 | 0 | 28.33 | 20.49 | 34 | FAIL |
| prior_low_smt_long_1000_1130 | 9 | 0 | 24.76 | 15.71 | 28 | FAIL |
| prior_low_smt_long_1030_1200 | 9 | 0 | 22.04 | 13.66 | 22 | FAIL |
| prior_two_sided_smt_1000_1130 | 9 | 0 | 57.13 | 38.24 | 62 | FAIL |

Machine summary:

```json
{
  "all_rows_density_pass": false,
  "audit_date": "2026-06-30",
  "campaign_id": "nq_chartfanatics_smt_po3_midpoint_reversion",
  "declared_entry_rows": 45,
  "density_fail_rows": 45,
  "density_pass_rows": 0,
  "full_end_date": "2026-06-09",
  "full_sessions": 3807,
  "full_start_date": "2011-01-03",
  "latest_252_end_date": "2026-06-09",
  "latest_252_start_date": "2025-06-04",
  "limited_end_date": "2012-09-06",
  "limited_sessions": 369,
  "limited_start_date": "2011-02-22"
}
```

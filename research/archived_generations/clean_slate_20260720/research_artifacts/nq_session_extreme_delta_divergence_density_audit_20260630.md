# nq_session_extreme_delta_divergence density audit

- Audit date: 2026-06-30
- Full window: 2011-01-03 to 2026-06-12 (3813 sessions)
- Limited-core window: 2011-02-22 to 2012-09-07 (371 sessions)
- Latest-252 window: 2025-06-09 to 2026-06-12
- Declared entry rows: 20
- Density passes: 20
- Density failures: 0

Gate: each declared entry row must produce at least 50 signals/year in full history, at least 50 signals/year in the limited-core window, and at least 50 signals in the latest 252 sessions before any PnL is inspected.

| variant | rows | pass rows | min full/year | min limited/year | min latest-252 | verdict |
|---|---:|---:|---:|---:|---:|---|
| afternoon_high_delta_divergence_short | 4 | 4 | 84.26 | 80.83 | 79 | PASS |
| afternoon_low_delta_divergence_long | 4 | 4 | 66.35 | 63.85 | 62 | PASS |
| midday_two_sided_delta_divergence | 4 | 4 | 200.19 | 195.62 | 204 | PASS |
| morning_high_delta_divergence_short | 4 | 4 | 146.59 | 148.08 | 147 | PASS |
| morning_low_delta_divergence_long | 4 | 4 | 133.24 | 129.06 | 131 | PASS |

Machine summary:

```json
{
  "all_rows_density_pass": true,
  "audit_date": "2026-06-30",
  "campaign_id": "nq_session_extreme_delta_divergence",
  "declared_entry_rows": 20,
  "density_fail_rows": 0,
  "density_pass_rows": 20,
  "full_end_date": "2026-06-12",
  "full_sessions": 3813,
  "full_start_date": "2011-01-03",
  "latest_252_end_date": "2026-06-12",
  "latest_252_start_date": "2025-06-09",
  "limited_end_date": "2012-09-07",
  "limited_sessions": 371,
  "limited_start_date": "2011-02-22"
}
```

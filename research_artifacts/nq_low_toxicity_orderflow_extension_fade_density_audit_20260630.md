# nq_low_toxicity_orderflow_extension_fade density audit

- Audit date: 2026-06-30
- Full window: 2011-01-03 to 2026-06-12 (3813 sessions)
- Limited-core window: 2011-02-22 to 2012-09-07 (371 sessions)
- Latest-252 window: 2025-06-09 to 2026-06-12
- Declared entry rows: 45
- Density passes: 43
- Density failures: 2

Gate: each declared entry row must produce at least 50 signals/year in full history, at least 50 signals/year in the limited-core window, and at least 50 signals in the latest 252 sessions before any PnL is inspected.

| variant | rows | pass rows | min full/year | min limited/year | min latest-252 | verdict |
|---|---:|---:|---:|---:|---:|---|
| three_slot_down_extension_fade_long | 9 | 9 | 67.68 | 66.57 | 71 | PASS |
| three_slot_up_extension_fade_short | 9 | 9 | 90.21 | 76.75 | 98 | PASS |
| two_slot_late_balanced_extension_fade | 9 | 9 | 55.78 | 53.66 | 59 | PASS |
| two_slot_midday_balanced_extension_fade | 9 | 8 | 50.62 | 44.15 | 54 | FAIL |
| two_slot_morning_balanced_extension_fade | 9 | 8 | 53.66 | 47.55 | 53 | FAIL |

Machine summary:

```json
{
  "all_rows_density_pass": false,
  "audit_date": "2026-06-30",
  "campaign_id": "nq_low_toxicity_orderflow_extension_fade",
  "declared_entry_rows": 45,
  "density_fail_rows": 2,
  "density_pass_rows": 43,
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

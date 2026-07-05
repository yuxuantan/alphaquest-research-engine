# nq_trade_fragmentation_liquidity_reversion density audit

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
| day_60m_fragmented_two_sided_fade | 9 | 9 | 129.87 | 98.49 | 153 | PASS |
| midday_30m_fragmented_down_fade_long | 9 | 9 | 70.65 | 52.98 | 90 | PASS |
| midday_30m_fragmented_up_fade_short | 9 | 7 | 60.01 | 41.43 | 64 | FAIL |
| morning_15m_fragmented_down_fade_long | 9 | 9 | 71.24 | 53.66 | 78 | PASS |
| morning_15m_fragmented_up_fade_short | 9 | 9 | 58.89 | 52.30 | 60 | PASS |

Machine summary:

```json
{
  "all_rows_density_pass": false,
  "audit_date": "2026-06-30",
  "campaign_id": "nq_trade_fragmentation_liquidity_reversion",
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

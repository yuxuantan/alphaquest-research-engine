# nq_chartfanatics_liquidity_inversion_fvg density audit

- Audit date: 2026-06-30
- Full window: 2011-01-03 to 2026-06-12 (3813 sessions)
- Limited-core window: 2011-02-22 to 2012-09-07 (371 sessions)
- Latest-252 window: 2025-06-09 to 2026-06-12
- Declared entry rows: 45
- Density passes: 36
- Density failures: 9

Gate: each declared entry row must produce at least 50 signals/year in full history, at least 50 signals/year in the limited-core window, and at least 50 signals in the latest 252 sessions before any PnL is inspected.

| variant | rows | pass rows | min full/year | min limited/year | min latest-252 | verdict |
|---|---:|---:|---:|---:|---:|---|
| prior_high_buy_side_fvg_inversion_short_1000 | 9 | 4 | 40.91 | 19.70 | 60 | FAIL |
| prior_low_sell_side_fvg_inversion_long_1000 | 9 | 5 | 36.68 | 36.00 | 46 | FAIL |
| prior_session_two_sided_fvg_inversion_1000 | 9 | 9 | 109.51 | 67.92 | 145 | PASS |
| session_high_buy_side_fvg_inversion_short_1000 | 9 | 9 | 103.96 | 61.81 | 131 | PASS |
| session_low_sell_side_fvg_inversion_long_1000 | 9 | 9 | 107.79 | 76.08 | 139 | PASS |

Machine summary:

```json
{
  "all_rows_density_pass": false,
  "audit_date": "2026-06-30",
  "campaign_id": "nq_chartfanatics_liquidity_inversion_fvg",
  "declared_entry_rows": 45,
  "density_fail_rows": 9,
  "density_pass_rows": 36,
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

# ES Prior-Session Breakout Orderflow Confirmation Density Audit

Date: 2026-06-17

No PnL, fills, stops, targets, equity, or trade outcomes were inspected. This audit counts raw completed-bar entry signals per year across the declared entry parameter grid only.

Data: `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
Period loaded for density: `2011-01-03 09:30:00-05:00` to `2026-06-09 15:55:00-04:00` (15.43 years)

| Variant | Entry combos | Min signals/year | Median signals/year | Max signals/year | Decision |
|---|---:|---:|---:|---:|---|
| `all_day_large10_buffer_break_two_sided` | 8 | 51.1 | 57.8 | 58.6 | eligible |
| `all_day_large20_no_buffer_break_two_sided` | 4 | 54.3 | 55.2 | 55.2 | eligible |
| `all_day_signed_buffer_break_two_sided` | 8 | 55.7 | 63.2 | 64.0 | eligible |
| `all_day_signed_high_volume_break_two_sided` | 12 | 54.2 | 61.2 | 63.8 | eligible |
| `first_half_signed_no_buffer_break_two_sided` | 4 | 55.2 | 55.9 | 55.9 | eligible |

Conclusion: all five variants are eligible for staged testing under the pre-PnL trade-frequency screen.

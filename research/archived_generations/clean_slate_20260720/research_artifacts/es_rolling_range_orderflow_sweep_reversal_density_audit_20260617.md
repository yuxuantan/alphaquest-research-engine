# ES Rolling Range Orderflow Sweep Reversal Density Audit

Date: 2026-06-17

No PnL, fills, stops, targets, equity, or trade outcomes were inspected. This audit counts raw completed-bar entry signals per year across the declared entry parameter grid only.

Data: `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
Period loaded for density: `2011-01-03 09:30:00-05:00` to `2026-06-09 15:55:00-04:00` (15.43 years)

| Variant | Entry combos | Min signals/year | Median signals/year | Max signals/year | Decision |
|---|---:|---:|---:|---:|---|
| `afternoon_signed_24bar_sweep_reclaim_1500` | 9 | 122.6 | 175.6 | 223.1 | eligible |
| `all_day_large20_36bar_sweep_reclaim_1500` | 9 | 82.4 | 173.0 | 237.3 | eligible |
| `midday_signed_24bar_sweep_reclaim_1400` | 9 | 88.5 | 183.9 | 237.6 | eligible |
| `morning_large10_12bar_sweep_reclaim_1130` | 9 | 76.4 | 160.9 | 227.5 | eligible |
| `morning_signed_12bar_sweep_reclaim_1130` | 9 | 56.1 | 148.0 | 227.7 | eligible |

Conclusion: all five variants are eligible for staged testing under the pre-PnL trade-frequency screen.

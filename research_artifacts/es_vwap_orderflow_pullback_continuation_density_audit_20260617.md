# ES VWAP Orderflow Pullback Continuation Density Audit - 2026-06-17

Scope: pre-PnL signal-density audit only. No profitability, stop, target, or
trade result fields were inspected.

Data: local Sierra ES RTH aggregate-orderflow cache
`data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`,
5-minute strategy bars, `2011-01-03` through `2026-06-09`.

Selected variants and raw signal density across declared entry grids:

| Variant | Flow | Window ET | Min signals/year | Median signals/year | Max signals/year |
| --- | --- | --- | ---: | ---: | ---: |
| `morning_signed_trend_reclaim_two_sided` | signed volume | 09:45-12:00 | 61.18 | 90.47 | 125.79 |
| `morning_large10_trend_reclaim_two_sided` | large10 | 09:45-12:00 | 78.87 | 101.29 | 127.09 |
| `morning_large20_trend_reclaim_two_sided` | large20 | 09:45-12:00 | 82.82 | 104.47 | 126.89 |
| `midday_large10_trend_reclaim_two_sided` | large10 | 11:00-14:30 | 53.27 | 66.82 | 85.35 |
| `midday_large20_trend_reclaim_two_sided` | large20 | 11:00-14:30 | 55.34 | 67.92 | 85.22 |

Rejected before testing:

| Candidate | Reason |
| --- | --- |
| `midday_signed_trend_reclaim_two_sided` | strict grid corner fell to 41.67 signals/year |
| `afternoon_signed_trend_reclaim_two_sided` | strict grid corner fell to 17.69 signals/year |
| `late_signed_failed_break_reclaim_two_sided` | strict grid corner fell to 11.99 signals/year |
| opening-drive pullback variants | initial formulation did not let the module observe opening bars when `start_time` was set after the drive window; rejected before PnL rather than patched into a result-seeking variant |

Decision: the five selected variants are eligible for predeclared staged testing
from a trade-density perspective. This does not imply profitability.

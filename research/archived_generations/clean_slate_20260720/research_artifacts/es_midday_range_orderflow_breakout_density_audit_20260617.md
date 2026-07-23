# ES Midday Range Orderflow Breakout Density Audit

Date: 2026-06-17

Scope: pre-PnL signal-density screen for `es_midday_range_orderflow_breakout`.

Data: local Sierra ES RTH 1-minute aggregate-orderflow cache
`data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`,
aggregated to 5-minute strategy bars from 2011-01-03 through 2026-06-09. No
external data and no paid download were used.

Method: count the first completed post-range breakout signal per RTH session
using only the completed midday range and the completed 5-minute confirmation
bar. Counts are raw signal counts before stop/target filtering, slippage,
commissions, position sizing, and staged PnL tests. The goal is only to reject
parameter spaces that cannot plausibly satisfy the 50 trades/year requirement.

Declared final variants:

| Variant | Range | Last Entry | Flow | Declared Entry Grid | Raw Signals/Year Range |
| --- | --- | --- | --- | --- | --- |
| `lunch_1130_1300_signed_breakout_1430` | 11:30-13:00 ET | 14:30 ET | signed volume | `max_range_points=[8,12,16]`, `min_orderflow_imbalance=[0.0,0.03,0.06]` | 64.22 to 132.34 |
| `lunch_1130_1300_large10_breakout_1430` | 11:30-13:00 ET | 14:30 ET | large-10 signed volume | `max_range_points=[8,12,16]`, `min_orderflow_imbalance=[0.0,0.05,0.10]` | 62.21 to 130.59 |
| `lunch_1130_1300_large20_breakout_1430` | 11:30-13:00 ET | 14:30 ET | large-20 signed volume | `max_range_points=[8,12,16]`, `min_orderflow_imbalance=[0.0,0.05,0.10]` | 62.67 to 129.61 |
| `late_lunch_1200_1330_signed_breakout_1500` | 12:00-13:30 ET | 15:00 ET | signed volume | `max_range_points=[8,12,16]`, `min_orderflow_imbalance=[0.0,0.03,0.06]` | 73.17 to 141.99 |
| `late_lunch_1200_1330_large10_breakout_1500` | 12:00-13:30 ET | 15:00 ET | large-10 signed volume | `max_range_points=[8,12,16]`, `min_orderflow_imbalance=[0.0,0.05,0.10]` | 70.70 to 139.85 |

Rejected before PnL:

- A wider `11:00-13:00 ET` midday range with signed-flow confirmation was not
  selected because some declared strict corners fell below 50 raw signals/year.
- One-sided directional-only versions were not selected because they would halve
  the opportunity set and make WFA trade density less likely without adding a
  distinct economic edge.
- Additional filters such as VWAP side, prior-day trend, or opening-range state
  were not added because they would duplicate active rejected families and
  reduce trade density.

Conclusion: the five final variants are eligible for staged testing from a
density standpoint. This audit does not establish profitability.

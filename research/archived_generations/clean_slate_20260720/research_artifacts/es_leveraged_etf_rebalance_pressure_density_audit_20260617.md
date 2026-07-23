# ES Leveraged ETF Rebalance Pressure Density Audit

Date: 2026-06-17

Source cache:
`data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`

Sample: 2011-01-03 through 2026-06-09, RTH completed 1-minute bars.

Method:

- Previous RTH close was taken from the prior session's final RTH close.
- Signal return is `signal_close / prev_rth_close - 1`.
- Signal rows are the bars closing at 14:30, 15:00, 15:15, and 15:30 ET.
- This is a pre-performance density check only; no PnL, stop, target, or
  post-signal outcome was inspected.

Prospective signals per year for declared threshold grid:

| Signal time | Threshold | Two-sided/year | Up/year | Down/year |
| --- | ---: | ---: | ---: | ---: |
| 14:30 | 20 bp | 180.9 | 101.7 | 79.2 |
| 14:30 | 30 bp | 154.2 | 87.9 | 66.3 |
| 14:30 | 40 bp | 131.8 | 75.3 | 56.5 |
| 15:00 | 20 bp | 182.8 | 103.8 | 79.0 |
| 15:00 | 30 bp | 155.8 | 89.9 | 65.9 |
| 15:00 | 40 bp | 133.6 | 76.6 | 57.0 |
| 15:30 | 20 bp | 182.4 | 102.8 | 79.6 |
| 15:30 | 30 bp | 157.2 | 89.6 | 67.7 |
| 15:30 | 40 bp | 135.8 | 77.5 | 58.3 |

Conclusion: all five proposed variant shapes are dense enough to be eligible
for staged testing before performance is known.

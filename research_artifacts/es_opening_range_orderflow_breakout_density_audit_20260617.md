# ES Opening Range Orderflow Breakout Density Audit - 2026-06-17

Purpose: pre-PnL screen for the price-action plus aggregate-orderflow campaign before
running staged tests.

Data source: `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`

Prepared strategy bars:
- Timeframe: 5-minute bars aggregated from local 1-minute RTH Sierra bars.
- Period: 2011-01-03 09:30:00 America/New_York through 2026-06-09 15:59:00 America/New_York.
- Rows: 297,726.
- Approximate span: 15.4305 years.
- No paid data was downloaded or requested.

Entry grid checked:
- `entry.params.breakout_buffer_ticks`: `[0, 2, 4]`
- `entry.params.min_orderflow_imbalance`: `[0.02, 0.06, 0.10]`
- Stop/target grid was not used for the first signal-density count.
- OR-edge stop feasibility was separately checked with the strictest entry corner.

Minimum entry signal density across declared entry grid corners:

| Variant | Strictest entry corner count | Strictest entry corner trades/year | Min entry-grid trades/year |
|---|---:|---:|---:|
| `or15_signed_flow_breakout_1030` | 1,444 | 93.58 | 93.58 |
| `or30_signed_flow_breakout_1100` | 1,417 | 91.83 | 91.83 |
| `or15_large10_flow_breakout_1030` | 2,125 | 137.71 | 137.71 |
| `or30_large20_flow_breakout_1100` | 1,994 | 129.22 | 129.22 |
| `or60_signed_flow_breakout_1200` | 1,275 | 82.63 | 82.63 |

OR-edge stop-cap feasibility at strictest entry corner (`breakout_buffer_ticks=4`,
`min_orderflow_imbalance=0.10`):

| Variant | Strict signals | Kept with 16-point cap | Kept with 24-point cap | Kept with 30-point cap |
|---|---:|---:|---:|---:|
| `or15_signed_flow_breakout_1030` | 1,444 | 1,196 | 1,352 | 1,401 |
| `or30_signed_flow_breakout_1100` | 1,417 | 1,109 | 1,284 | 1,344 |
| `or15_large10_flow_breakout_1030` | 2,125 | 1,502 | 1,862 | 1,997 |
| `or30_large20_flow_breakout_1100` | 1,994 | 1,304 | 1,677 | 1,828 |
| `or60_signed_flow_breakout_1200` | 1,275 | 873 | 1,084 | 1,174 |

Decision: approve density for staged testing. Every declared entry corner exceeds
50 signals/year, and the strictest entry corner remains above 50/year even with
the tightest declared OR-edge stop cap of 16 points.

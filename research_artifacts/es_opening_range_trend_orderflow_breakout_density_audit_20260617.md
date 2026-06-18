# ES Opening-Range Trend Orderflow Breakout Density Audit

Date: 2026-06-17

Data: local Sierra ES RTH 1-minute aggregate-orderflow parquet, aggregated to completed 5-minute bars.

No PnL, fills, stops, targets, or outcome metrics were used. The screen only checks pre-test signal density for the declared entry grids.

| Variant | Signals/year range across declared entry grid | Eligible |
|---|---:|---|
| `or15_signed_trend_breakout_1030` | 114.1 to 170.8 | yes |
| `or15_large10_trend_breakout_1030` | 122.7 to 162.9 | yes |
| `or30_signed_trend_breakout_1100` | 111.4 to 180.6 | yes |
| `or30_large20_trend_breakout_1130` | 119.1 to 177.7 | yes |
| `or60_signed_trend_breakout_1200` | 77.9 to 155.5 | yes |

Conclusion: all five variants exceed the 50 trades/year pre-PnL density floor at every declared entry-grid corner.

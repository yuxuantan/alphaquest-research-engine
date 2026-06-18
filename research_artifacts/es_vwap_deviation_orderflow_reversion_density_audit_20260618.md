# ES VWAP deviation orderflow reversion density audit - 2026-06-18

Scope: pre-PnL signal-density check only. Counts used the actual `vwap_deviation_orderflow_reversion` entry module on completed 5-minute bars. No PnL, stops, targets, WFA, monkey, Monte Carlo, or holdout results were inspected.

Data:
- Source: `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
- Strategy timeframe: `5m`
- Full configured period: `2011-01-03` through `2026-06-09`
- Benchmark limited-core window: `2011-02-22` through `2012-09-06`

Strict density corner:
- `entry.params.min_vwap_deviation_ticks = 16`
- `entry.params.min_counterflow_imbalance = 0.04`
- fixed `min_close_location_long = 0.35`
- fixed `max_close_location_short = 0.65`
- one signal/trade maximum per day

| Variant | Full signals/year | Limited-core signals/year | Full signals | Limited signals |
|---|---:|---:|---:|---:|
| `morning_signed_counterflow_1200` | 149.31 | 91.64 | 2304 | 141 |
| `morning_large10_counterflow_1200` | 154.69 | 90.34 | 2387 | 139 |
| `midday_signed_counterflow_1400` | 183.92 | 137.13 | 2838 | 211 |
| `midday_large20_counterflow_1400` | 184.83 | 133.23 | 2852 | 205 |
| `afternoon_signed_counterflow_1530` | 192.73 | 152.73 | 2974 | 235 |

Decision: approve for staged testing. Every final variant exceeds the 50 trades/year feasibility floor at the strictest declared entry-grid corner in both full-history and the seeded limited-core window. No PnL or result-driven parameter choice was used.

# ES opening-drive VWAP orderflow pullback density audit - 2026-06-18

Scope: pre-PnL signal-density check only. This audit counted completed-bar entry signals using the actual `vwap_orderflow_pullback_continuation` entry module in `opening_drive_pullback` mode. It did not inspect trade PnL, stops, targets, equity curves, WFA, monkey, Monte Carlo, or holdout results.

Data:
- Source: `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
- Strategy timeframe: `5m`
- Full configured period: `2011-01-03` through `2026-06-09`
- Benchmark limited-core window: `2011-02-22` through `2012-09-06`
- Limited-core window policy: seeded random 10 percent period, seed `31`, excluding the latest 10 percent of available data and the configured Covid avoid range.

Important mechanics note:
- `entry.params.start_time` must be `09:30:00` for this module in `opening_drive_pullback` mode because the existing module uses `start_time` to begin state collection. The signal still cannot exist until the opening-drive window has completed and a later VWAP pullback/reclaim is observed.

Rejected before PnL:
- `15m_signed_drive_pullback_1130` and `15m_large10_drive_pullback_1130` were rejected because the strict corner produced only `26.65` limited-window signals/year.

Strict density corner used for final variants:
- `entry.params.min_drive_points = 4.0`
- `entry.params.min_orderflow_imbalance = 0.04`
- fixed `pullback_tolerance_ticks = 4`
- fixed `reclaim_window_bars = 6`
- fixed `min_drive_close_location = 0.55`
- one signal/trade maximum per day

| Variant | Full signals/year | Limited-core signals/year | Full signals | Limited signals |
|---|---:|---:|---:|---:|
| `drive30_signed_pullback_1230` | 81.59 | 53.29 | 1259 | 82 |
| `drive30_large10_pullback_1230` | 86.52 | 53.29 | 1335 | 82 |
| `drive30_large20_pullback_1230` | 86.26 | 51.34 | 1331 | 79 |
| `drive60_signed_pullback_1430` | 92.41 | 83.19 | 1426 | 128 |
| `drive60_large20_pullback_1430` | 96.37 | 83.19 | 1487 | 128 |

Decision: approve for staged testing. Every final variant exceeds the 50 trades/year feasibility floor at the strictest declared entry-grid corner in both full-history and the seeded limited-core window. No PnL or result-driven parameter choice was used.

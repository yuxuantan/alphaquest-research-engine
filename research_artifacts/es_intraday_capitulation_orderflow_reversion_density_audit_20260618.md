# ES intraday capitulation orderflow reversion density audit - 2026-06-18

Scope: pre-PnL signal-density check only. This audit counted completed-bar entry signals using the actual `intraday_capitulation_mr` entry module after the module was tightened to session-local RSI/volume history and completed-window signed-volume imbalance. It did not inspect trade PnL, stops, targets, equity curves, WFA, monkey, Monte Carlo, or holdout results.

Data:
- Source: `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
- Full configured period: `2011-01-03` through `2026-06-09`
- Benchmark limited-core window: `2011-02-22` through `2012-09-06`
- Limited-core window policy: seeded random 10 percent period, seed `31`, excluding the latest 10 percent of available data and the configured Covid avoid range.

Strict density corner:
- `entry.params.max_rsi = 35`
- `entry.params.min_sell_imbalance = 0.04`
- fixed `min_volume_ratio = 1.3`
- fixed `min_down_move_ticks = 4`
- fixed `max_close_location_from_low = 0.30`
- one signal/trade maximum per day

| Variant | Full signals/year | Limited-core signals/year | Full signals | Limited signals |
|---|---:|---:|---:|---:|
| `all_day_5m_capitulation_long_1530` | 143.09 | 157.28 | 2208 | 242 |
| `late_day_5m_capitulation_long_1530` | 126.18 | 127.38 | 1947 | 196 |
| `afternoon_5m_capitulation_long_1530` | 106.15 | 109.19 | 1638 | 168 |
| `all_day_10m_capitulation_long_1530` | 76.34 | 83.19 | 1178 | 128 |
| `late_day_10m_capitulation_long_1530` | 74.59 | 75.39 | 1151 | 116 |

Decision: approve for staged testing. Every variant exceeds the 50 trades/year feasibility floor at the strictest declared entry-grid corner in both full-history and the seeded limited-core window. No PnL or result-driven parameter choice was used.

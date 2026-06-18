# ES Session Open Orderflow Reclaim Density Audit - 2026-06-18

Scope: density-only audit before any PnL test for `es_session_open_orderflow_reclaim`.

Data: local Sierra ES completed 1-minute RTH cache `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`.

Benchmark limited-core window: 2011-02-22 through 2012-09-06, matching the current random 10% shortlist window seed and exclusions.

Declared entry grid: `min_open_extension_ticks = [6, 8, 12]` and `min_orderflow_imbalance = [0.20, 0.30, 0.40]`. Stop and target grids are not part of the signal-density count.

| Variant | Direction | Flow mode | Limited min signals/year | Limited max signals/year | Full min signals/year | Full max signals/year | Decision |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `morning_down_open_reclaim_long` | `long` | `large10` | 74.7 | 153.4 | 118.4 | 168.4 | approve for testing |
| `morning_up_open_reject_short` | `short` | `large10` | 72.8 | 150.1 | 111.2 | 162.3 | approve for testing |
| `midday_large10_two_sided_open_reclaim` | `both` | `large10` | 140.4 | 191.1 | 169.5 | 205.0 | approve for testing |
| `afternoon_large20_down_open_reclaim_long` | `long` | `large20` | 102.7 | 142.3 | 121.0 | 148.5 | approve for testing |
| `afternoon_large20_up_open_reject_short` | `short` | `large20` | 81.9 | 121.5 | 104.7 | 131.1 | approve for testing |

Interpretation: every declared entry-grid corner clears the 50 trades/year feasibility floor in the benchmark window and over full available local history before PnL is inspected. This does not imply profitability; it only prevents wasting staged tests on a mechanically sparse variant.

Lookahead note: the density logic requires the away-from-open excursion to be present on a prior completed bar before the signal bar closes through the RTH open. Same-bar extension/reclaim sequences are intentionally excluded.

# ES Morning Orderflow Momentum Continuation Density Audit - 2026-06-19

This is a pre-PnL signal-density audit. It counts at most one completed opening-window signal per session and does not inspect stop, target, trade PnL, WFA, monkey, or Monte Carlo results.

Data: `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`.
Full window: 2011-01-03 through 2026-06-09. Limited-core methodology window: 2011-02-22 through 2012-09-06, matching the seeded 10% random-fraction shortlist window that avoids the latest holdout and COVID period.

| Variant | Entry threshold grid | Full min signals/year | Limited-core min signals/year | Decision |
|---|---:|---:|---:|---|
| `first30_signed_flow_continuation_1000` | `return_ticks=[4, 8, 12]; flow=[0.01, 0.02, 0.03]` | 61.9 | 79.3 | approve for staged testing |
| `first45_large10_flow_continuation_1015` | `return_ticks=[6, 10, 14]; flow=[0.02, 0.04, 0.06]` | 66.6 | 57.2 | approve for staged testing |
| `first60_signed_flow_continuation_1030` | `return_ticks=[6, 10, 14]; flow=[0.005, 0.015, 0.025]` | 59.4 | 98.1 | approve for staged testing |
| `first60_large20_flow_continuation_1030` | `return_ticks=[8, 12, 16]; flow=[0.02, 0.04, 0.06]` | 78.0 | 59.1 | approve for staged testing |
| `first90_broad_large_alignment_1100` | `return_ticks=[8, 12, 16]; flow=[0.005, 0.01, 0.02]` | 56.6 | 89.7 | approve for staged testing |

The first draft used stricter flow thresholds that would have produced sub-50/year strict corners. Those thresholds were relaxed before any PnL or trade outcome was inspected.

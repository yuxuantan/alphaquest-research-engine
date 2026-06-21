# ES Morning Orderflow Momentum Continuation Rescue Attempt 1 Density Audit - 2026-06-19

This is a pre-PnL rescue density audit. It counts at most one signal per session and does not inspect trade PnL or outcomes.

| Variant | Rescue entry grid | Full min signals/year | Limited-core min signals/year | Decision |
|---|---:|---:|---:|---|
| `first30_signed_flow_continuation_1000` | `return_ticks=[10, 12, 14]; flow=[0.02, 0.025, 0.03]` | 56.4 | 63.7 | approve rescue testing |
| `first45_large10_flow_continuation_1015` | `return_ticks=[10, 12, 14]; flow=[0.04, 0.05, 0.06]` | 66.6 | 57.2 | approve rescue testing |
| `first60_signed_flow_continuation_1030` | `return_ticks=[10, 12, 14]; flow=[0.015, 0.02, 0.025]` | 59.4 | 98.1 | approve rescue testing |
| `first60_large20_flow_continuation_1030` | `return_ticks=[14, 16, 18]; flow=[0.015, 0.02, 0.03]` | 90.8 | 75.4 | approve rescue testing |
| `first90_broad_large_alignment_1100` | `return_ticks=[12, 16, 20]; flow=[0.005, 0.01, 0.015]` | 63.8 | 79.9 | approve rescue testing |

TP grids are unchanged from original configs and remain `[1.0, 1.5, 2.0]`; the rescue does not lower reward:risk below 1.0R.

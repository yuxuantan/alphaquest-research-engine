# ES opening gap orderflow continuation reformulated density audit - 2026-06-18

No paid data was downloaded. This uses the local Sierra ES aggregate-orderflow cache only.

Full subset: `2011-01-03` through `2026-06-09`; limited-core subset: `2011-02-22` through `2012-09-06`.

| variant | strict entry overrides | full signals/year | limited signals/year | full side counts | limited side counts |
|---|---:|---:|---:|---:|---:|
| `early_large10_gap_hold_continuation_1000` | `{"entry.params.min_opening_gap_ticks": 10, "entry.params.min_orderflow_imbalance": 0.08}` | 52.55 | 55.25 | `{'long': 498, 'short': 298}` | `{'long': 41, 'short': 41}` |
| `early_signed_gap_hold_continuation_1000` | `{"entry.params.min_opening_gap_ticks": 10, "entry.params.min_orderflow_imbalance": 0.04}` | 57.70 | 67.38 | `{'long': 521, 'short': 353}` | `{'long': 50, 'short': 50}` |
| `late_morning_large10_gap_hold_continuation_1100` | `{"entry.params.min_opening_gap_ticks": 10, "entry.params.min_orderflow_imbalance": 0.08}` | 47.40 | 57.27 | `{'long': 411, 'short': 307}` | `{'long': 40, 'short': 45}` |
| `midday_signed_gap_hold_continuation_1200` | `{"entry.params.min_opening_gap_ticks": 10, "entry.params.min_orderflow_imbalance": 0.04}` | 46.94 | 49.86 | `{'long': 421, 'short': 290}` | `{'long': 45, 'short': 29}` |
| `morning_signed_gap_hold_continuation_1030` | `{"entry.params.min_opening_gap_ticks": 10, "entry.params.min_orderflow_imbalance": 0.04}` | 44.10 | 76.14 | `{'long': 404, 'short': 264}` | `{'long': 62, 'short': 51}` |

Decision: reject_or_reformulate_before_pnl.

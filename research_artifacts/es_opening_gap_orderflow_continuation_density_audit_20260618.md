# ES opening gap orderflow continuation density audit - 2026-06-18

No paid data was downloaded. This uses the local Sierra ES aggregate-orderflow cache only.

Full subset: `2011-01-03` through `2026-06-09`; limited-core subset: `2011-02-22` through `2012-09-06`.

| variant | strict entry overrides | full signals/year | limited signals/year | full side counts | limited side counts |
|---|---:|---:|---:|---:|---:|
| `early_large10_gap_hold_continuation_1000` | `{"entry.params.min_opening_gap_ticks": 12, "entry.params.min_orderflow_imbalance": 0.1}` | 49.05 | 53.23 | `{'long': 465, 'short': 278}` | `{'long': 39, 'short': 40}` |
| `early_signed_gap_hold_continuation_1000` | `{"entry.params.min_opening_gap_ticks": 12, "entry.params.min_orderflow_imbalance": 0.05}` | 57.70 | 67.38 | `{'long': 521, 'short': 353}` | `{'long': 50, 'short': 50}` |
| `late_morning_large10_gap_hold_continuation_1100` | `{"entry.params.min_opening_gap_ticks": 12, "entry.params.min_orderflow_imbalance": 0.1}` | 44.89 | 53.23 | `{'long': 393, 'short': 287}` | `{'long': 38, 'short': 41}` |
| `midday_signed_gap_hold_continuation_1200` | `{"entry.params.min_opening_gap_ticks": 12, "entry.params.min_orderflow_imbalance": 0.05}` | 46.94 | 49.86 | `{'long': 421, 'short': 290}` | `{'long': 45, 'short': 29}` |
| `morning_signed_gap_hold_continuation_1030` | `{"entry.params.min_opening_gap_ticks": 12, "entry.params.min_orderflow_imbalance": 0.05}` | 44.10 | 76.14 | `{'long': 404, 'short': 264}` | `{'long': 62, 'short': 51}` |

Decision: reject_or_reformulate_before_pnl.

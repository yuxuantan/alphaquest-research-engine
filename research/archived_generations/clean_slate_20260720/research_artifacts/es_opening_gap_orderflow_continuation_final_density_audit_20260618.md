# ES opening gap orderflow continuation final density audit - 2026-06-18

No paid data was downloaded. This uses the local Sierra ES aggregate-orderflow cache only.

Full subset: `2011-01-03` through `2026-06-09`; limited-core subset: `2011-02-22` through `2012-09-06`.

| variant | strict entry overrides | full signals/year | limited signals/year | full side counts | limited side counts |
|---|---:|---:|---:|---:|---:|
| `early_large10_gap_hold_continuation_1000` | `{"entry.params.min_opening_gap_ticks": 8, "entry.params.min_orderflow_imbalance": 0.04}` | 61.66 | 65.36 | `{'long': 584, 'short': 350}` | `{'long': 50, 'short': 47}` |
| `early_signed_gap_hold_continuation_1000` | `{"entry.params.min_opening_gap_ticks": 8, "entry.params.min_orderflow_imbalance": 0.02}` | 69.12 | 74.12 | `{'long': 619, 'short': 428}` | `{'long': 55, 'short': 55}` |
| `late_morning_large10_gap_hold_continuation_1100` | `{"entry.params.min_opening_gap_ticks": 8, "entry.params.min_orderflow_imbalance": 0.04}` | 54.73 | 64.01 | `{'long': 467, 'short': 362}` | `{'long': 46, 'short': 49}` |
| `midday_signed_gap_hold_continuation_1200` | `{"entry.params.min_opening_gap_ticks": 8, "entry.params.min_orderflow_imbalance": 0.02}` | 57.97 | 59.29 | `{'long': 515, 'short': 363}` | `{'long': 54, 'short': 34}` |
| `morning_signed_gap_hold_continuation_1030` | `{"entry.params.min_opening_gap_ticks": 8, "entry.params.min_orderflow_imbalance": 0.02}` | 57.17 | 81.53 | `{'long': 515, 'short': 351}` | `{'long': 65, 'short': 56}` |

Decision: approve_for_testing.

# ES prior-session flip retest orderflow rescue density audit - 2026-06-18

No paid data was downloaded. This uses the local Sierra ES aggregate-orderflow cache only.

Limited-core subset: `2011-02-22` through `2012-09-06`.

| variant | strict entry overrides | full signals/year | limited signals/year | full side counts | limited side counts |
|---|---:|---:|---:|---:|---:|
| `afternoon_large10_aligned_two_sided_flip` | `{"entry.params.min_orderflow_imbalance": 0.015, "entry.params.retest_window_bars": 4}` | 92.89 | 96.35 | `{'long': 756, 'short': 651}` | `{'long': 76, 'short': 67}` |
| `late_morning_large10_absorbed_two_sided_flip` | `{"entry.params.min_orderflow_imbalance": 0.015, "entry.params.retest_window_bars": 4}` | 108.87 | 121.28 | `{'long': 951, 'short': 698}` | `{'long': 95, 'short': 85}` |
| `midday_signed_aligned_two_sided_flip` | `{"entry.params.min_orderflow_imbalance": 0.01, "entry.params.retest_window_bars": 4}` | 113.23 | 112.52 | `{'long': 949, 'short': 766}` | `{'long': 86, 'short': 81}` |
| `morning_signed_absorbed_two_sided_flip` | `{"entry.params.min_orderflow_imbalance": 0.01, "entry.params.retest_window_bars": 2}` | 93.02 | 105.11 | `{'long': 836, 'short': 573}` | `{'long': 85, 'short': 71}` |
| `morning_signed_aligned_two_sided_flip` | `{"entry.params.min_orderflow_imbalance": 0.01, "entry.params.retest_window_bars": 2}` | 104.84 | 109.16 | `{'long': 907, 'short': 681}` | `{'long': 88, 'short': 74}` |

Decision: approve_rescue_for_testing.

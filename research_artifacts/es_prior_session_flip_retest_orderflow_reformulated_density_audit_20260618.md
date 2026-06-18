# ES prior-session flip retest orderflow reformulated density audit - 2026-06-18

No paid data was downloaded. This audit uses the local Sierra ES aggregate-orderflow cache only.

Full subset: `2011-01-03` through `2026-06-09`; sessions `3817`, years proxy `15.15`.
Limited-core shortlist subset from canonical random 10% window: `2011-02-22` through `2012-09-06`; sessions `374`, years proxy `1.48`.

Strict density corner uses the shortest declared retest window and highest declared orderflow threshold for each variant. Stop and target grids do not affect signal count.

| variant | strict entry overrides | full signals/year | limited signals/year | full side counts | limited side counts |
|---|---:|---:|---:|---:|---:|
| `afternoon_large10_aligned_two_sided_flip` | `{"entry.params.min_orderflow_imbalance": 0.005, "entry.params.retest_window_bars": 4}` | 92.89 | 96.35 | `{'long': 756, 'short': 651}` | `{'long': 76, 'short': 67}` |
| `late_morning_large10_absorbed_two_sided_flip` | `{"entry.params.min_orderflow_imbalance": 0.005, "entry.params.retest_window_bars": 4}` | 108.87 | 121.28 | `{'long': 951, 'short': 698}` | `{'long': 95, 'short': 85}` |
| `midday_signed_aligned_two_sided_flip` | `{"entry.params.min_orderflow_imbalance": 0.003, "entry.params.retest_window_bars": 4}` | 113.23 | 112.52 | `{'long': 949, 'short': 766}` | `{'long': 86, 'short': 81}` |
| `morning_signed_absorbed_two_sided_flip` | `{"entry.params.min_orderflow_imbalance": 0.003, "entry.params.retest_window_bars": 4}` | 93.02 | 105.11 | `{'long': 836, 'short': 573}` | `{'long': 85, 'short': 71}` |
| `morning_signed_aligned_two_sided_flip` | `{"entry.params.min_orderflow_imbalance": 0.003, "entry.params.retest_window_bars": 4}` | 104.84 | 109.16 | `{'long': 907, 'short': 681}` | `{'long': 88, 'short': 74}` |

Decision: approve_for_testing.

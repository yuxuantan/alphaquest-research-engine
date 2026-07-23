# ES prior-session flip retest orderflow density audit - 2026-06-18

No paid data was downloaded. This audit uses the local Sierra ES aggregate-orderflow cache only.

Full subset: `2011-01-03` through `2026-06-09`; sessions `3817`, years proxy `15.15`.
Limited-core shortlist subset from canonical random 10% window: `2011-02-22` through `2012-09-06`; sessions `374`, years proxy `1.48`.

Strict density corner uses the shortest declared retest window and highest declared orderflow threshold for each variant. Stop and target grids do not affect signal count.

| variant | strict entry overrides | full signals/year | limited signals/year | full side counts | limited side counts |
|---|---:|---:|---:|---:|---:|
| `afternoon_large20_aligned_two_sided_flip` | `{"entry.params.min_orderflow_imbalance": 0.01, "entry.params.retest_window_bars": 2}` | 7.66 | 8.76 | `{'long': 56, 'short': 60}` | `{'long': 5, 'short': 8}` |
| `late_morning_large10_aligned_two_sided_flip` | `{"entry.params.min_orderflow_imbalance": 0.01, "entry.params.retest_window_bars": 2}` | 17.43 | 21.56 | `{'long': 128, 'short': 136}` | `{'long': 16, 'short': 16}` |
| `midday_signed_aligned_two_sided_flip` | `{"entry.params.min_orderflow_imbalance": 0.005, "entry.params.retest_window_bars": 3}` | 14.06 | 12.13 | `{'long': 120, 'short': 93}` | `{'long': 7, 'short': 11}` |
| `morning_signed_absorption_pdh_support_flip_long` | `{"entry.params.min_orderflow_imbalance": 0.005, "entry.params.retest_window_bars": 2}` | 6.21 | 6.06 | `{'long': 94, 'short': 0}` | `{'long': 9, 'short': 0}` |
| `morning_signed_absorption_pdl_resistance_flip_short` | `{"entry.params.min_orderflow_imbalance": 0.005, "entry.params.retest_window_bars": 2}` | 5.22 | 6.06 | `{'long': 0, 'short': 79}` | `{'long': 0, 'short': 9}` |

Decision: reject_or_reformulate_before_pnl.

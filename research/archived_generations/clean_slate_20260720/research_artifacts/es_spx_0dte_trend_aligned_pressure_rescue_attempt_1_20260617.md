# ES SPX 0DTE Trend-Aligned Pressure Rescue Attempt 1 - 2026-06-17

Decision: one parameter-space rescue is authorized for each failed original
variant because all five originals failed `limited_core_grid_test`.

Original outcome:

| Variant | Stage | Profitable combos | Failure |
| --- | --- | ---: | --- |
| `all_0dte_trend_only_1330` | limited core | 0.6667 | Below 0.70 profitable-combo gate; no benchmark-passing combo |
| `all_0dte_trend_only_1500` | limited core | 0.1111 | Below 0.70 profitable-combo gate; no benchmark-passing combo |
| `all_0dte_trend_continuation_1330` | limited core | 0.6667 | Below 0.70 profitable-combo gate; no benchmark-passing combo |
| `all_0dte_trend_continuation_1400` | limited core | 0.0000 | Below 0.70 profitable-combo gate; no benchmark-passing combo |
| `all_0dte_trend_continuation_1500` | limited core | 0.0000 | Below 0.70 profitable-combo gate; no benchmark-passing combo |

Rescue boundaries:

- Entry module remains `spx_0dte_trend_aligned_pressure`.
- Calendar bucket remains `all_available`.
- Signal times remain unchanged.
- Trend windows remain fixed at 30 minutes and 120 minutes.
- Direction logic remains unchanged.
- Stop module remains `percent_from_entry`.
- Target module remains `fixed_r`.
- Data period remains `2016-02-24` through `2026-06-09`.
- Only fixed parameters and declared parameter grids are changed.

Rescue parameter spaces:

| Variant | Entry grid | Stop grid | Target grid | Combinations |
| --- | --- | --- | --- | ---: |
| `all_0dte_trend_only_1330` | fixed | `[0.002, 0.0025, 0.003, 0.004]` | `[1.0, 1.5, 2.0]` | 12 |
| `all_0dte_trend_only_1500` | fixed | `[0.002, 0.0025, 0.003]` | `[0.5, 0.75, 1.0]` | 9 |
| `all_0dte_trend_continuation_1330` | `[0, 4, 8]` ticks | `[0.002, 0.0025, 0.003, 0.004]` | `[1.0, 1.5, 2.0]` | 36 |
| `all_0dte_trend_continuation_1400` | `[0, 4, 8]` ticks | `[0.0008, 0.001, 0.00125, 0.0015]` | `[0.5, 0.75, 1.0]` | 36 |
| `all_0dte_trend_continuation_1500` | `[0, 4, 8]` ticks | `[0.002, 0.0025, 0.003]` | `[0.5, 0.75, 1.0]` | 27 |

This is the only allowed rescue attempt for these failed variants.

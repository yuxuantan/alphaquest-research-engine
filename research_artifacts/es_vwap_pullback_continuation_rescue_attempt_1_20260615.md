# ES VWAP Pullback Continuation Rescue Attempt 1

Date: 2026-06-15

Decision: FAIL

All five original variants failed. One parameter-space-only rescue was run for each failed variant without changing entry, stop, target, timeframe, data window, stage criteria, or the VWAP pullback-continuation mechanic.

| Variant | Run | Terminal stage | Profitable combo rate | Monkey profitable rate | Top net | Top trades | Notes |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `failed_vwap_break_two_sided` | `run1` | `limited_core_grid_test` | 0.12345679012345678 |  | 1161.25 | 34 | original |
| `failed_vwap_break_two_sided` | `rescue1` | `limited_core_grid_test` | 0.24691358024691357 |  | 2180.0 | 9 | rescue consumed |
| `midday_trend_reclaim_two_sided` | `run1` | `limited_core_grid_test` | 0.2222222222222222 |  | 3295.0 | 61 | original |
| `midday_trend_reclaim_two_sided` | `rescue1` | `limited_monkey_test` | 0.8148148148148148 | 0.18 | 3392.5 | 89 | rescue consumed |
| `morning_opening_drive_pullback_long` | `run1` | `limited_core_grid_test` | 0.1728395061728395 |  | 1526.25 | 51 | original |
| `morning_opening_drive_pullback_long` | `rescue1` | `limited_core_grid_test` | 0.14814814814814814 |  | 1807.5 | 51 | rescue consumed |
| `morning_opening_drive_pullback_short` | `run1` | `limited_core_grid_test` | 0.037037037037037035 |  | 591.25 | 58 | original |
| `morning_opening_drive_pullback_short` | `rescue1` | `limited_core_grid_test` | 0.2345679012345679 |  | 1988.125 | 58 | rescue consumed |
| `morning_trend_reclaim_two_sided` | `run1` | `limited_core_grid_test` | 0.012345679012345678 |  | 184.375 | 80 | original |
| `morning_trend_reclaim_two_sided` | `rescue1` | `limited_core_grid_test` | 0.1111111111111111 |  | 725.0 | 35 | rescue consumed |

The strongest rescue by core stability was `midday_trend_reclaim_two_sided/rescue1`, with `0.8148148148148148` profitable core combinations. It failed `limited_monkey_test` with only `0.18` profitable monkey paths and median net profit of `-3210.0`, so no WFA, Monte Carlo, or frozen validation was reached.

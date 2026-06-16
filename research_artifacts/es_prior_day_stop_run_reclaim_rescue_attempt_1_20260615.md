# ES Prior-Day Stop-Run Reclaim Rescue Attempt 1

Date: 2026-06-15

Decision: FAIL

All five original variants failed. One parameter-space-only rescue was run for each failed variant without changing entry, stop, target, timeframe, data window, stage criteria, or the core prior-day stop-run reclaim mechanic.

| Variant | Run | Terminal stage | Profitable combo rate | Monkey profitable rate | Top net | Top trades | Notes |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `afternoon_two_sided_reclaim` | `run1` | `limited_core_grid_test` | 0.12345679012345678 |  | 653.125 | 15 | original |
| `afternoon_two_sided_reclaim` | `rescue1` | `limited_core_grid_test` | 0.345679012345679 |  | 933.75 | 17 | rescue consumed |
| `full_session_two_sided_reclaim` | `run1` | `limited_core_grid_test` | 0.012345679012345678 |  | 301.875 | 54 | original |
| `full_session_two_sided_reclaim` | `rescue1` | `limited_core_grid_test` | 0.2716049382716049 |  | 880.0 | 54 | rescue consumed |
| `midday_two_sided_reclaim` | `run1` | `limited_core_grid_test` | 0.2716049382716049 |  | 763.75 | 11 | original |
| `midday_two_sided_reclaim` | `rescue1` | `limited_core_grid_test` | 0.2222222222222222 |  | 763.75 | 11 | rescue consumed |
| `morning_prior_high_reject_short` | `run1` | `limited_core_grid_test` | 0.14814814814814814 |  | 1162.5 | 20 | original |
| `morning_prior_high_reject_short` | `rescue1` | `limited_monkey_test` | 0.8641975308641975 | 0.32666666666666666 | 2673.75 | 24 | rescue consumed |
| `morning_prior_low_reclaim_long` | `run1` | `limited_core_grid_test` | 0.1728395061728395 |  | 1143.125 | 22 | original |
| `morning_prior_low_reclaim_long` | `rescue1` | `limited_core_grid_test` | 0.654320987654321 |  | 1803.75 | 23 | rescue consumed |

The strongest rescue by core stability was `morning_prior_high_reject_short/rescue1`, with 0.8641975308641975 profitable core combinations. It failed `limited_monkey_test` with only 0.32666666666666666 profitable monkey paths and median net profit of -770.0, so no WFA, Monte Carlo, or frozen validation was reached.

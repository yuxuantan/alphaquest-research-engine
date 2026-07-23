# NQ SPX 0DTE Expiration Pressure - Campaign Summary

Verdict: FAIL

The campaign did not produce a candidate strategy. `full_week_late_move_continuation_1430` passed the limited core grid and monkey test, but failed stitched WFA with negative OOS net profit, PF below 1.0, and early exit. The four fade variants failed the limited core grid and were not advanced.

| Variant | Terminal stage | Core profitable | Top net | Top PF | Top trades | Top MAR | Monkey | WFA | WFA net | WFA PF | WFA MAR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| full_week_down_move_fade_long_1000 | limited_core_grid_test | 0/18 | -5092.5 | 0.7029746281714786 | 27 | -2.2735343807649504 | skipped | skipped | None | None | None |
| full_week_late_move_continuation_1430 | walk_forward_analysis | 18/18 | 26275.0 | 2.3013868251609706 | 72 | 23.219010921573528 | passed | failed | -4677.5 | 0.9419016271270649 | -0.19314201987022375 |
| full_week_up_move_fade_short_1000 | limited_core_grid_test | 4/18 | 3765.0 | 1.2036786583716528 | 48 | 3.11842964423106 | skipped | skipped | None | None | None |
| mwf_two_sided_fade_1030 | limited_core_grid_test | 11/18 | 8395.0 | 1.574017094017094 | 43 | 9.848652460043429 | skipped | skipped | None | None | None |
| tue_thu_two_sided_fade_1030 | limited_core_grid_test | 11/18 | 10695.0 | 1.6094017094017095 | 38 | 9.413969979710018 | skipped | skipped | None | None | None |

No rescue was authorized or used.

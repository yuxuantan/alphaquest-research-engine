# NQ Realized Semivariance Asymmetry - Campaign Summary

Verdict: FAIL

Two variants passed the limited core grid but failed the monkey robustness gate. Three variants failed the core grid. No variant reached WFA, downstream Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

| Variant | Terminal stage | Core profitable | Top net | Top PF | Monkey | Monkey profitable | Monkey median net | WFA net | WFA PF | WFA MAR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| high_1d_badvol_rebound_long_1000 | limited_core_grid_test | 7/18 | 1295.0 | 1.1731283422459893 | skipped | None | None | None | None | None |
| high_1d_badvol_continuation_short_1030 | limited_monkey_test | 27/27 | 4875.0 | 1.2375730994152048 | failed | 0.216625 | -2000.0 | None | None | None |
| high_downside_share_rebound_long_1130 | limited_core_grid_test | 11/18 | 2712.5 | 1.3297872340425532 | skipped | None | None | None | None | None |
| high_goodvol_fade_short_1200 | limited_monkey_test | 16/18 | 1558.75 | 1.1681499460625675 | failed | 0.208125 | -1585.0 | None | None | None |
| two_sided_5d_bad_good_balance_1330 | limited_core_grid_test | 0/18 | -48.75 | 0.9947944474105713 | skipped | None | None | None | None | None |

No rescue was authorized or used.

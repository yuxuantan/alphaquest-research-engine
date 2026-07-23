# NQ Cboe VIX Term Structure Intraday - Campaign Test Summary

Verdict: FAIL

No variant passed the full staged workflow. The campaign is rejected without a NQ rescue attempt.

| variant | terminal_stage | core profitable | core top net | core PF | core trades | monkey status | WFA status | failure |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| backwardation_short_1000 | limited_core_grid_test | 3/27 | 862.5 | 1.1005830903790088 | 77 | skipped | skipped | failed limited core grid gate |
| backwardation_surge_short_1330 | limited_core_grid_test | 9/27 | 715.0 | 1.0671361502347418 | 127 | skipped | skipped | failed limited core grid gate |
| contango_long_1030 | limited_monkey_test | 27/27 | 4365.0 | 1.3460166468489894 | 139 | failed | skipped | failed limited monkey/randomized schedule gate |
| curve_flattening_short_1200 | walk_forward_analysis | 22/27 | 2147.5 | 1.1595468053491829 | 122 | passed | failed | failed walk-forward analysis gate |
| front_stress_short_1130 | walk_forward_analysis | 25/27 | 1775.0 | 1.1997749015194148 | 89 | passed | failed | failed walk-forward analysis gate |

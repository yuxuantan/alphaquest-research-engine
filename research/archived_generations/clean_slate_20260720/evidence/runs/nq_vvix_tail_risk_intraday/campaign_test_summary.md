# NQ VVIX Tail Risk Intraday - Campaign Test Summary

Verdict: FAIL

No variant passed the full staged workflow. The campaign is rejected without a NQ rescue attempt.

| variant | terminal_stage | core profitable | core top net | core PF | core trades | monkey status | failure |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| falling_vvix_long_1200 | limited_core_grid_test | 7/27 | 775.0 | 1.0689195197865717 | 132 | skipped | failed limited core grid gate |
| high_vvix_short_1000 | limited_core_grid_test | 0/18 | -120.0 | 0.9891255097417309 | 152 | skipped | failed limited core grid gate |
| high_vvix_vix_ratio_short_1330 | limited_core_grid_test | 0/27 | -2070.0 | 0.7994186046511628 | 140 | skipped | failed limited core grid gate |
| low_vvix_long_1030 | limited_monkey_test | 27/27 | 1780.0 | 1.2479108635097493 | 76 | failed | failed limited monkey/randomized schedule gate |
| rising_vvix_short_1130 | limited_monkey_test | 23/27 | 2202.5 | 1.1480672268907564 | 129 | failed | failed limited monkey/randomized schedule gate |

# nq_archive_intraday_momentum_retest / long_only_1030_strength_balanced

Use completed NQ RTH bars from 09:30 ET through each signal time; the active rule tests a single 10:30 long strength slot with the archived 200 bps maximum source-range cap centered in the grid, then flattens by 15:59 ET unless the fixed slot stop or fixed-R target is hit.

Parameter grid: 9 combinations, capped to at most two entry parameters, one stop parameter, and one target parameter before testing.

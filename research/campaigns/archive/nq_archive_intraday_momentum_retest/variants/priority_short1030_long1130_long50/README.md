# nq_archive_intraday_momentum_retest / priority_short1030_long1130_long50

Use completed NQ RTH bars from 09:30 ET through each signal time; the active rule tests first a 10:30 short weakness slot, then an 11:30 long strength slot with the archived long threshold centered at 50 bps, then flattens by 15:59 ET unless the fixed slot stop or fixed-R target is hit.

Parameter grid: 9 combinations, capped to at most two entry parameters, one stop parameter, and one target parameter before testing.

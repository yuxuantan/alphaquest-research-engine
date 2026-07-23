# nq_archive_intraday_momentum_retest / short_only_1030_weakness

Use completed NQ RTH bars from 09:30 ET through each signal time; the active rule tests a single 10:30 short weakness slot that isolates the short side of the archived priority rule, then flattens by 15:59 ET unless the fixed slot stop or fixed-R target is hit.

Parameter grid: 9 combinations, capped to at most two entry parameters, one stop parameter, and one target parameter before testing.

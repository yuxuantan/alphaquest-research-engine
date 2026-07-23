# nq_opening_gap_orderflow_continuation campaign test summary

Decision: FAIL

No NQ opening-gap continuation variant completed the full staged flow: two variants failed limited_monkey_test after core and three failed limited_core_grid_test.

| Variant | Stage | Profitable | Benchmark pass | Top net | Top PF | Top trades | Top failure |
|---|---:|---:|---:|---:|---:|---:|---|
| early_signed_gap_hold_continuation_1000 | limited_monkey_test | 81/81 (1.0000) | 15 | 4860.0 | 1.5463743676222597 | 79 |  |
| late_morning_large10_gap_hold_continuation_1100 | limited_core_grid_test | 6/81 (0.0741) | 0 | 325.0 | 1.0752314814814814 | 39 | min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |
| late_morning_large20_gap_hold_continuation_1100 | limited_core_grid_test | 15/81 (0.1852) | 0 | 945.0 | 1.2302070645554202 | 31 | min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |
| midday_signed_gap_hold_continuation_1200 | limited_core_grid_test | 7/81 (0.0864) | 0 | 575.0 | 1.201401050788091 | 27 | min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |
| morning_signed_gap_hold_continuation_1030 | limited_monkey_test | 58/81 (0.7160) | 0 | 3585.0 | 1.456687898089172 | 70 | min_trades_per_year;preferred_min_total_trades |

Notes:
- early_signed_gap_hold_continuation_1000 passed core with 81/81 profitable combinations but failed monkey with net beat 0.870875 and drawdown beat 0.565.
- morning_signed_gap_hold_continuation_1030 barely cleared core at 58/81 profitable combinations and failed monkey on net beat 0.754125.
- The large10, large20, and midday signed variants failed limited_core_grid_test.
- No rescue was authorized or applied.

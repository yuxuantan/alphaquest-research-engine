# nq_opening_gap_orderflow_absorption_fade campaign test summary

Decision: FAIL

All five NQ opening-gap absorption fade variants failed limited_core_grid_test; no monkey, WFA, Monte Carlo, simulated incubation, or acceptance stages were reached.

| Variant | Stage | Profitable | Benchmark pass | Top net | Top PF | Top trades | Top failure |
|---|---:|---:|---:|---:|---:|---:|---|
| early_signed_gap_absorption_fade_1000 | limited_core_grid_test | 11/81 (0.1358) | 0 | 865.0 | 1.3634453781512605 | 50 | min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |
| late_morning_large10_gap_absorption_fade_1100 | limited_core_grid_test | 28/81 (0.3457) | 0 | 525.0 | 1.1593323216995448 | 52 | min_trades_per_year;max_consecutive_losses;preferred_min_total_trades;max_best_day_concentration |
| late_morning_large20_gap_absorption_fade_1100 | limited_core_grid_test | 0/81 (0.0000) | 0 | -270.0 | 0.9230769230769231 | 53 | min_total_net_profit;min_trades_per_year;max_consecutive_losses;preferred_min_total_trades |
| midday_signed_gap_absorption_fade_1200 | limited_core_grid_test | 0/81 (0.0000) | 0 | -480.0 | 0.8714859437751004 | 48 | min_total_net_profit;min_trades_per_year;preferred_min_total_trades |
| morning_signed_gap_absorption_fade_1030 | limited_core_grid_test | 1/81 (0.0123) | 0 | 680.0 | 1.0928327645051195 | 109 | max_best_day_concentration |

Notes:
- Best profitable-combo rate was late_morning_large10_gap_absorption_fade_1100 at 28/81 = 0.3457, below the 0.70 gate.
- Gap-fill-fraction targets caused some target-already-reached entry rejections but the dominant failure was weak core profitability and benchmark stability.
- No rescue was authorized or applied.

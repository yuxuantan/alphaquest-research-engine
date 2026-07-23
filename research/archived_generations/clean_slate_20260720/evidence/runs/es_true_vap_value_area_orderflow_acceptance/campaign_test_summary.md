# ES True VAP Value-Area Orderflow Acceptance

Verdict: FAIL

All eight predeclared true-VAP value-area orderflow acceptance variants failed limited_core_grid_test. No variant reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

| Variant | Profitable | Benchmark | Top Net | PF | MAR | Trades/Yr | Failure |
|---|---:|---:|---:|---:|---:|---:|---|
| morning_inside_value_escape_signed_two_sided_1130 | 4/81 | 0 | 377.5 | 1.037 | 0.123 | 60.1 | max_best_day_concentration |
| morning_gap_above_vah_hold_footprint_long_1030 | 0/81 | 0 | -477.5 | 0.969 | -0.111 | 90.3 | min_total_net_profit |
| morning_true_vah_signed_acceptance_long_1130 | 0/81 | 0 | -695.0 | 0.967 | -0.127 | 127.0 | min_total_net_profit;max_consecutive_losses |
| morning_gap_below_val_hold_footprint_short_1030 | 0/81 | 0 | -730.0 | 0.940 | -0.182 | 76.3 | min_total_net_profit |
| morning_true_val_signed_acceptance_short_1130 | 0/81 | 0 | -3321.25 | 0.839 | -0.444 | 122.6 | min_total_net_profit;max_consecutive_losses |
| late_morning_true_value_large10_two_sided_1230 | 0/81 | 0 | -6617.5 | 0.830 | -0.517 | 231.7 | min_total_net_profit;max_consecutive_losses |
| afternoon_true_value_signed_two_sided_1500 | 0/81 | 0 | -10839.375 | 0.689 | -0.638 | 228.5 | min_total_net_profit;max_consecutive_losses |
| midday_true_value_large20_two_sided_1400 | 0/81 | 0 | -11443.75 | 0.565 | -0.645 | 227.8 | min_total_net_profit;max_consecutive_losses |

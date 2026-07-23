# NQ/ES Relative-Value Orderflow Absorption Reversion Summary

Decision: FAIL

All five variants failed `limited_core_grid_test`; no run reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

| Variant | Profitable combos | Benchmark combos | Top net | Top PF | Top MAR | Trades/year | Failure |
|---|---:|---:|---:|---:|---:|---:|---|
| late_morning30_two_sided_absorption_1130 | 0/81 (0.000) | 0 | -4010.00 | 0.814 | -0.401 | 174.2 | min_total_net_profit;max_consecutive_losses |
| midday60_two_sided_absorption_1400 | 1/81 (0.012) | 0 | 167.50 | 1.010 | 0.029 | 152.7 | max_consecutive_losses;max_best_day_concentration |
| morning15_two_sided_absorption_1000 | 0/81 (0.000) | 0 | -1437.50 | 0.940 | -0.368 | 162.1 | min_total_net_profit;max_consecutive_losses |
| morning30_outperform_absorption_short_1030 | 0/81 (0.000) | 0 | -1165.00 | 0.932 | -0.275 | 116.7 | min_total_net_profit |
| morning30_underperform_absorption_long_1030 | 6/81 (0.074) | 0 | 612.50 | 1.085 | 0.230 | 70.4 | max_consecutive_losses |

No rescue was run because no rescue was explicitly authorized for this NQ campaign.

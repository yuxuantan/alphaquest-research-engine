# NQ Leveraged ETF Rebalance Pressure - Campaign Summary

Verdict: FAIL

All five variants failed the limited core grid with zero profitable parameter combinations. No variant reached monkey robustness, WFA, downstream Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

| Variant | Terminal stage | Core profitable | Top net | Top PF | Top trades | Top MAR |
|---|---:|---:|---:|---:|---:|---:|
| two_sided_day_move_1430 | limited_core_grid_test | 0/9 | -5025.0 | 0.6993718217170206 | 206 | -0.6549131787243975 |
| two_sided_day_move_1500 | limited_core_grid_test | 0/9 | -4010.0 | 0.7750350631136045 | 256 | -0.6117376497969091 |
| up_day_rebalance_long_1500 | limited_core_grid_test | 0/9 | -1755.0 | 0.7770012706480305 | 147 | -0.5551012655920772 |
| down_day_rebalance_short_1500 | limited_core_grid_test | 0/9 | -1830.0 | 0.7596848325673013 | 117 | -0.5777809466923997 |
| late_acceleration_two_sided_1530 | limited_core_grid_test | 0/27 | -2260.0 | 0.6869806094182825 | 125 | -0.5698480237944572 |

No rescue was authorized or used.

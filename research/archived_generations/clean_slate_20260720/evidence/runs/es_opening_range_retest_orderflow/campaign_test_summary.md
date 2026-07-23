# ES Opening-Range Retest Orderflow Campaign Summary

Decision: **FAIL**

All five original variants and all five one-time parameter-space rescues failed limited_core_grid_test before monkey, WFA, Monte Carlo, simulated incubation, or frozen validation.

| Variant | Run | Terminal stage | Profitable combo rate | Top net | Top PF | Top trades/year | Top failure |
|---|---|---|---:|---:|---:|---:|---|
| `or15_signed_absorption_retest_1030` | `run1` | `limited_core_grid_test` | 0.0000 | -935.00 | 0.8519 | 71.58 | min_total_net_profit |
| `or15_signed_absorption_retest_1030` | `rescue1` | `limited_core_grid_test` | 0.0000 | -353.12 | 0.9695 | 102.38 | min_total_net_profit |
| `or15_signed_aligned_retest_1030` | `run1` | `limited_core_grid_test` | 0.0000 | -2502.50 | 0.8127 | 105.31 | min_total_net_profit;max_consecutive_losses |
| `or15_signed_aligned_retest_1030` | `rescue1` | `limited_core_grid_test` | 0.0000 | -1126.25 | 0.8866 | 89.30 | min_total_net_profit |
| `or30_large10_absorption_retest_1130` | `run1` | `limited_core_grid_test` | 0.0000 | -2037.50 | 0.6890 | 78.97 | min_total_net_profit |
| `or30_large10_absorption_retest_1130` | `rescue1` | `limited_core_grid_test` | 0.0247 | 1184.38 | 1.0835 | 105.10 |  |
| `or30_signed_absorption_retest_1100` | `run1` | `limited_core_grid_test` | 0.0000 | -1540.00 | 0.8147 | 73.57 | min_total_net_profit |
| `or30_signed_absorption_retest_1100` | `rescue1` | `limited_core_grid_test` | 0.0123 | 53.75 | 1.0040 | 93.11 | max_best_day_concentration |
| `or60_large20_aligned_retest_1230` | `run1` | `limited_core_grid_test` | 0.0000 | -2972.50 | 0.7383 | 95.88 | min_total_net_profit |
| `or60_large20_aligned_retest_1230` | `rescue1` | `limited_core_grid_test` | 0.0000 | -245.00 | 0.9864 | 106.96 | min_total_net_profit |

No run reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

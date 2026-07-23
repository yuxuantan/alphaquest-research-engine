# ES Opening Range Orderflow Breakout Campaign Summary

Decision: **FAIL**

All five original variants and all five one-time parameter-space rescues failed limited_core_grid_test before monkey, WFA, Monte Carlo, simulated incubation, or frozen validation.

| Variant | Run | Terminal stage | Profitable combo rate | Top net | Top PF | Top trades/year | Top failure |
|---|---|---|---:|---:|---:|---:|---|
| `or15_large10_flow_breakout_1030` | `rescue1` | `limited_core_grid_test` | 0.0000 | -3825.00 | 0.8890 | 175.41 | min_total_net_profit |
| `or15_large10_flow_breakout_1030` | `run1` | `limited_core_grid_test` | 0.0000 | -3825.00 | 0.8890 | 175.41 | min_total_net_profit |
| `or15_signed_flow_breakout_1030` | `rescue1` | `limited_core_grid_test` | 0.0000 | -3920.62 | 0.8862 | 176.06 | min_total_net_profit |
| `or15_signed_flow_breakout_1030` | `run1` | `limited_core_grid_test` | 0.0000 | -3920.62 | 0.8862 | 176.06 | min_total_net_profit |
| `or30_large20_flow_breakout_1100` | `rescue1` | `limited_core_grid_test` | 0.0000 | -1870.00 | 0.9364 | 142.53 | min_total_net_profit |
| `or30_large20_flow_breakout_1100` | `run1` | `limited_core_grid_test` | 0.0000 | -1870.00 | 0.9364 | 142.53 | min_total_net_profit |
| `or30_signed_flow_breakout_1100` | `rescue1` | `limited_core_grid_test` | 0.0000 | -3211.25 | 0.8958 | 147.09 | min_total_net_profit |
| `or30_signed_flow_breakout_1100` | `run1` | `limited_core_grid_test` | 0.0000 | -3211.25 | 0.8958 | 147.09 | min_total_net_profit |
| `or60_signed_flow_breakout_1200` | `rescue1` | `limited_core_grid_test` | 0.0000 | -3044.38 | 0.8321 | 89.66 | min_total_net_profit |
| `or60_signed_flow_breakout_1200` | `run1` | `limited_core_grid_test` | 0.0741 | 267.50 | 1.0201 | 61.52 | max_best_day_concentration |

No run reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

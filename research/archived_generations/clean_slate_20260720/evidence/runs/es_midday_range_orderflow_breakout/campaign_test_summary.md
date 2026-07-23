# ES Midday Range Orderflow Breakout Campaign Summary

Decision: **FAIL**

All five original variants and all five one-time parameter-space rescues failed limited_core_grid_test before monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

| Variant | Run | Terminal stage | Profitable combo rate | Top net | Top PF | Top trades/year | Top failure |
|---|---|---|---:|---:|---:|---:|---|
| `late_lunch_1200_1330_large10_breakout_1500` | `run1` | `limited_core_grid_test` | 0.0000 | -4603.75 | 0.7792 | 145.04 | min_total_net_profit;max_consecutive_losses |
| `late_lunch_1200_1330_large10_breakout_1500` | `rescue1` | `limited_core_grid_test` | 0.0000 | -2580.62 | 0.8870 | 161.74 | min_total_net_profit |
| `late_lunch_1200_1330_signed_breakout_1500` | `run1` | `limited_core_grid_test` | 0.0000 | -5018.75 | 0.7633 | 147.00 | min_total_net_profit;max_consecutive_losses |
| `late_lunch_1200_1330_signed_breakout_1500` | `rescue1` | `limited_core_grid_test` | 0.0000 | -3005.00 | 0.8730 | 163.70 | min_total_net_profit;max_consecutive_losses |
| `lunch_1130_1300_large10_breakout_1430` | `run1` | `limited_core_grid_test` | 0.0000 | -5647.50 | 0.7126 | 125.66 | min_total_net_profit |
| `lunch_1130_1300_large10_breakout_1430` | `rescue1` | `limited_core_grid_test` | 0.0000 | -2588.75 | 0.8859 | 143.08 | min_total_net_profit |
| `lunch_1130_1300_large20_breakout_1430` | `run1` | `limited_core_grid_test` | 0.0000 | -5306.25 | 0.7313 | 127.63 | min_total_net_profit |
| `lunch_1130_1300_large20_breakout_1430` | `rescue1` | `limited_core_grid_test` | 0.0000 | -2433.75 | 0.8949 | 145.70 | min_total_net_profit |
| `lunch_1130_1300_signed_breakout_1430` | `run1` | `limited_core_grid_test` | 0.0000 | -5726.25 | 0.7104 | 126.97 | min_total_net_profit |
| `lunch_1130_1300_signed_breakout_1430` | `rescue1` | `limited_core_grid_test` | 0.0000 | -3238.75 | 0.8635 | 146.35 | min_total_net_profit |

No run reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

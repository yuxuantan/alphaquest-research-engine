

# ES Market Plumbing Liquidity Capacity Rescue Attempt 1

Decision: FAIL.

Scope: one rescue per failed variant. Rescues changed only neighboring feature-threshold parameter space and stop/target parameter values inside the same `market_plumbing_priority`, `percent_from_entry`, and `fixed_r` modules.

Results:

| Variant | Terminal stage | Profitable/monkey pct | Median net | Top net | Top PF | Top trades |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `dealer_lending_pressure_long_1130` | `limited_core_grid_test` | 0.2222222222222222 |  | 1675.625 | 1.1214441021924262 | 88 |
| `dealer_lending_pressure_long_1330` | `limited_core_grid_test` | 0.6666666666666666 |  | 3006.875 | 1.2639346061005048 | 88 |
| `vx_oi_stress_long_1330` | `limited_core_grid_test` | 0.6666666666666666 |  | 3167.5 | 1.2682049110922946 | 94 |
| `vx_oi_crowding_short_1330` | `limited_core_grid_test` | 0.0 |  | -904.375 | 0.8444086021505376 | 39 |
| `dual_pressure_priority_long_1130` | `limited_monkey_test` | 0.3466666666666667 | -1665.0 | 8212.5 | 1.3683974430862398 | 145 |

No rescue reached WFA, Monte Carlo, or frozen validation. No second rescue is permitted for these variants.

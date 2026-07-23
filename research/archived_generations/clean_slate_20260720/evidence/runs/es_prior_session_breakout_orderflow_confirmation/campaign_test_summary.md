# ES Prior-Session Breakout Orderflow Confirmation Campaign Summary

Decision: **FAIL**

All five original variants and all five one-time parameter-space rescues failed the staged methodology. The strongest rescue, first_half_signed_no_buffer_break_two_sided/rescue1, passed limited core and limited monkey but failed WFA early because the first selected in-sample profit factor was 0.887903893951947, below the required 1.0; no OOS trades were stitched and no Monte Carlo, incubation, frozen validation, or candidate report was reached.

| Variant | Run | Terminal stage | Profitable combo rate | Top net | Top PF | Top trades/year | Notes |
|---|---|---|---:|---:|---:|---:|---|
| `all_day_large10_buffer_break_two_sided` | `rescue1` | `limited_core_grid_test` | 0.0000 | -130.00 | 0.9857 | 59.45 | min_total_net_profit |
| `all_day_large10_buffer_break_two_sided` | `run1` | `limited_core_grid_test` | 0.1111 | 687.50 | 1.0962 | 49.00 | min_trades_per_year;preferred_min_total_trades |
| `all_day_large20_no_buffer_break_two_sided` | `rescue1` | `limited_core_grid_test` | 0.2222 | 205.62 | 1.0172 | 56.83 | max_best_day_concentration |
| `all_day_large20_no_buffer_break_two_sided` | `run1` | `limited_core_grid_test` | 0.0000 | -442.50 | 0.9490 | 56.18 | min_total_net_profit |
| `all_day_signed_buffer_break_two_sided` | `rescue1` | `limited_core_grid_test` | 0.0000 | -365.00 | 0.9608 | 60.76 | min_total_net_profit;max_consecutive_losses |
| `all_day_signed_buffer_break_two_sided` | `run1` | `limited_core_grid_test` | 0.1111 | 687.50 | 1.0962 | 49.00 | min_trades_per_year;preferred_min_total_trades |
| `all_day_signed_high_volume_break_two_sided` | `rescue1` | `limited_core_grid_test` | 0.2778 | 1671.25 | 1.1391 | 56.83 |  |
| `all_day_signed_high_volume_break_two_sided` | `run1` | `limited_core_grid_test` | 0.0000 | -97.50 | 0.9915 | 56.83 | min_total_net_profit |
| `first_half_signed_no_buffer_break_two_sided` | `rescue1` | `walk_forward_analysis` | 0.8056 | 1535.00 | 1.2074 | 54.22 | WFA early exit: selected_train_profit_factor_below_minimum train PF 0.887903893951947 |
| `first_half_signed_no_buffer_break_two_sided` | `run1` | `limited_core_grid_test` | 0.2222 | 1330.00 | 1.1748 | 54.88 |  |

No run reached WFA OOS monkey, WFA OOS Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

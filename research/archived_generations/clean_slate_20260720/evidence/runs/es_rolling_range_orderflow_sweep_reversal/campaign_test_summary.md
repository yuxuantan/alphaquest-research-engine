# ES Rolling Range Orderflow Sweep Reversal Campaign Summary

Decision: **FAIL**

All five original variants and all five one-time parameter-space/fixed-parameter rescues failed limited_core_grid_test before monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

| Variant | Run | Profitable combo rate | Top net | Top PF | Top trades/year | Failure |
|---|---|---:|---:|---:|---:|---|
| `afternoon_signed_24bar_sweep_reclaim_1500` | `rescue1` | 0.0370 | 675.00 | 1.4272 | 22.27 | min_trades_per_year;preferred_min_total_trades |
| `afternoon_signed_24bar_sweep_reclaim_1500` | `run1` | 0.0000 | -5941.25 | 0.5851 | 148.06 | min_total_net_profit;max_consecutive_losses |
| `all_day_large20_36bar_sweep_reclaim_1500` | `rescue1` | 0.0988 | 65.00 | 1.3881 | 5.49 | min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |
| `all_day_large20_36bar_sweep_reclaim_1500` | `run1` | 0.0000 | -3412.50 | 0.5699 | 76.51 | min_total_net_profit |
| `midday_signed_24bar_sweep_reclaim_1400` | `rescue1` | 0.0370 | 395.00 | 1.1540 | 28.97 | min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |
| `midday_signed_24bar_sweep_reclaim_1400` | `run1` | 0.0000 | -4578.75 | 0.3386 | 116.70 | min_total_net_profit |
| `morning_large10_12bar_sweep_reclaim_1130` | `rescue1` | 0.0000 | 0.00 | 0.0000 | 0.00 | min_trades_per_year;preferred_min_total_trades |
| `morning_large10_12bar_sweep_reclaim_1130` | `run1` | 0.0000 | -3741.25 | 0.2430 | 67.50 | min_total_net_profit;max_consecutive_losses |
| `morning_signed_12bar_sweep_reclaim_1130` | `rescue1` | 0.0000 | 0.00 | 0.0000 | 0.00 | min_trades_per_year;preferred_min_total_trades |
| `morning_signed_12bar_sweep_reclaim_1130` | `run1` | 0.0000 | -3621.88 | 0.2257 | 62.87 | min_total_net_profit;max_consecutive_losses |

No run reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

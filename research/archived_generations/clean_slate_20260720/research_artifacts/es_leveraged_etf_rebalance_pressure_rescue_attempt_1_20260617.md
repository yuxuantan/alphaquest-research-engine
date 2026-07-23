# ES Leveraged ETF Rebalance Pressure Rescue Attempt 1

Date: 2026-06-17

Decision: FAIL

## Scope

Campaign: `es_leveraged_etf_rebalance_pressure`

All five original variants failed `limited_core_grid_test`, so each failed
variant received exactly one rescue attempt.

Allowed rescue changes only:

- `entry.params.min_abs_day_return_bps` grids/defaults
- `entry.params.min_recent_return_bps` grid/default for `late_acceleration_two_sided_1530`
- `sl.params.stop_pct` grids/defaults
- `tp.params.target_r_multiple` grids/defaults

Unchanged:

- LETF rebalance-pressure edge thesis
- entry module `leveraged_etf_rebalance_pressure`
- setup mode, signal time, and direction rule per variant
- stop module `percent_from_entry`
- target module `fixed_r`
- local Sierra data source and sample window
- commissions, slippage, tick size, point value, session, prop rules, and stage gates

## Results

| Variant | Run | Profitable combo rate | Benchmark pass combos | Top net | Top PF | Top trades |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `two_sided_day_move_1430` | run1 | 0.0 | 0 | -6997.50 | 0.6587 | 237 |
| `two_sided_day_move_1430` | rescue1 | 0.0 | 0 | -5083.75 | 0.5545 | 193 |
| `two_sided_day_move_1500` | run1 | 0.0 | 0 | -6052.50 | 0.6994 | 263 |
| `two_sided_day_move_1500` | rescue1 | 0.0 | 0 | -6321.25 | 0.7213 | 263 |
| `up_day_rebalance_long_1500` | run1 | 0.0 | 0 | -2647.50 | 0.7292 | 142 |
| `up_day_rebalance_long_1500` | rescue1 | 0.0 | 0 | -1522.50 | 0.8379 | 142 |
| `down_day_rebalance_short_1500` | run1 | 0.0 | 0 | -2500.00 | 0.6302 | 110 |
| `down_day_rebalance_short_1500` | rescue1 | 0.0 | 0 | -2642.50 | 0.6418 | 116 |
| `late_acceleration_two_sided_1530` | run1 | 0.0 | 0 | -2715.00 | 0.6740 | 118 |
| `late_acceleration_two_sided_1530` | rescue1 | 0.0 | 0 | -1568.75 | 0.8182 | 115 |

## Conclusion

All original and rescue grids failed before monkey testing. No run reached WFA,
WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or
candidate reporting. The campaign is rejected.

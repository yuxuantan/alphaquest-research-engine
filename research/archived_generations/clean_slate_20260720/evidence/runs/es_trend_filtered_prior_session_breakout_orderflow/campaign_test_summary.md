# Campaign Test Summary

- Campaign: `es_trend_filtered_prior_session_breakout_orderflow`
- Decision: `FAIL`
- Terminal stage: `limited_core_grid_test`
- Original runs: `5`
- Rescue runs: `5`
- No run reached limited monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

## Best Runs

| Run | Variant | Profitable combo rate | Benchmark-pass combos | Top net | Top PF | Top trades/year | Top failure |
|---|---|---:|---:|---:|---:|---:|---|
| Best original | `first_half_signed_trend_hold_two_sided` | 0.0000 | 0 | -4866.25 | 0.6380 | 163.80 | min_total_net_profit |
| Best rescue | `all_day_large10_trend_hold_two_sided` | 0.0123 | 0 | 1052.50 | 1.0401 | 122.81 | max_best_day_concentration |

## Variant Results

| Variant | Run | Profitable combo rate | Benchmark-pass combos | Top net | Top PF | Top trades/year | Signals |
|---|---|---:|---:|---:|---:|---:|---:|
| `all_day_large10_trend_hold_two_sided` | `rescue1` | 0.0123 | 0 | 1052.50 | 1.0401 | 122.81 | 187 |
| `all_day_large10_trend_hold_two_sided` | `run1` | 0.0000 | 0 | -5552.50 | 0.6184 | 174.20 | 291 |
| `all_day_signed_high_volume_trend_hold_two_sided` | `rescue1` | 0.0000 | 0 | -3472.50 | 0.8278 | 121.51 | 187 |
| `all_day_signed_high_volume_trend_hold_two_sided` | `run1` | 0.0000 | 0 | -5550.00 | 0.6809 | 156.00 | 241 |
| `all_day_signed_trend_hold_two_sided` | `rescue1` | 0.0000 | 0 | -3365.00 | 0.9038 | 157.89 | 243 |
| `all_day_signed_trend_hold_two_sided` | `run1` | 0.0000 | 0 | -5761.25 | 0.6107 | 176.15 | 292 |
| `first_half_large10_trend_hold_two_sided` | `rescue1` | 0.0000 | 0 | -456.25 | 0.9671 | 95.43 | 145 |
| `first_half_large10_trend_hold_two_sided` | `run1` | 0.0000 | 0 | -4937.50 | 0.6320 | 162.50 | 273 |
| `first_half_signed_trend_hold_two_sided` | `rescue1` | 0.0000 | 0 | -2885.00 | 0.8818 | 144.28 | 222 |
| `first_half_signed_trend_hold_two_sided` | `run1` | 0.0000 | 0 | -4866.25 | 0.6380 | 163.80 | 271 |

Decision: FAIL.

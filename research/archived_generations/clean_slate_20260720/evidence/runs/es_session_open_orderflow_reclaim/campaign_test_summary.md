# Campaign Test Summary

- Campaign: `es_session_open_orderflow_reclaim`
- Decision: `FAIL`
- Terminal stage: `limited_core_grid_test`
- Original runs: `5`
- Rescue runs: `5`
- No run reached limited monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

## Best Runs

| Run | Variant | Profitable combo rate | Benchmark-pass combos | Top net | Top PF | Top trades/year | Top failure |
|---|---|---:|---:|---:|---:|---:|---|
| Best original | `morning_down_open_reclaim_long` | 0.0123 | 0 | 50.00 | 1.0062 | 74.87 | max_best_day_concentration |
| Best rescue | `morning_up_open_reject_short` | 0.0988 | 2 | 1572.50 | 1.1077 | 89.85 |  |

## Variant Results

| Variant | Run | Profitable combo rate | Benchmark-pass combos | Top net | Top PF | Top trades/year |
|---|---|---:|---:|---:|---:|---:|
| `afternoon_large20_down_open_reclaim_long` | `rescue1` | 0.0000 | 0 | -2437.50 | 0.8867 | 127.42 |
| `afternoon_large20_down_open_reclaim_long` | `run1` | 0.0000 | 0 | -3258.75 | 0.6660 | 103.26 |
| `afternoon_large20_up_open_reject_short` | `rescue1` | 0.0123 | 0 | 32.50 | 1.0018 | 91.79 |
| `afternoon_large20_up_open_reject_short` | `run1` | 0.0000 | 0 | -2705.00 | 0.6624 | 82.04 |
| `midday_large10_two_sided_open_reclaim` | `rescue1` | 0.0000 | 0 | -2352.50 | 0.9290 | 151.66 |
| `midday_large10_two_sided_open_reclaim` | `run1` | 0.0000 | 0 | -4392.50 | 0.7763 | 143.90 |
| `morning_down_open_reclaim_long` | `rescue1` | 0.0494 | 1 | 0.00 | 1.0000 | 74.86 |
| `morning_down_open_reclaim_long` | `run1` | 0.0123 | 0 | 50.00 | 1.0062 | 74.87 |
| `morning_up_open_reject_short` | `rescue1` | 0.0988 | 2 | 1572.50 | 1.1077 | 89.85 |
| `morning_up_open_reject_short` | `run1` | 0.0000 | 0 | -1422.50 | 0.8439 | 72.92 |

Decision: FAIL.

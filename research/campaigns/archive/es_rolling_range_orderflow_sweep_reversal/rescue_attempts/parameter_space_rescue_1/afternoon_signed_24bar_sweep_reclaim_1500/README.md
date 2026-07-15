# afternoon_signed_24bar_sweep_reclaim_1500 rescue1

Rescue keeps the same rolling-range sweep-reclaim plus aggregate-flow absorption mechanic. It changes only fixed parameters and declared parameter space.

```yaml
entry.params.lookback_bars: [36, 48, 60]
entry.params.min_absorption_imbalance: [0.02, 0.05, 0.08]
sl.params.stop_offset_ticks: [2, 4, 6]
tp.params.target_r_multiple: [1.0, 1.5, 2.0]
```

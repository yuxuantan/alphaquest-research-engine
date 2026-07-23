# friday_open_preweekend_long_0935 Rescue 1

Campaign: `es_day_of_week_seasonality`

This is the single allowed rescue for `friday_open_preweekend_long_0935`. It changes only the declared stop and target parameter space:

```yaml
sl.params.stop_pct: [0.0015, 0.003, 0.005]
tp.params.target_r_multiple: [0.75, 1.25, 1.75]
```

Retained: entry module, weekday/direction map, signal time, timeframe, data window, costs, fill assumptions, stage gates, and prop rules.

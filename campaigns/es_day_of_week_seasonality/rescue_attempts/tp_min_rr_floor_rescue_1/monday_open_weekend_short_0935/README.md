# monday_open_weekend_short_0935 Rescue 1

Campaign: `es_day_of_week_seasonality`

This is the single allowed rescue for `monday_open_weekend_short_0935`. It changes only the declared stop and target parameter space:

```yaml
sl.params.stop_pct: [0.0015, 0.003, 0.005]
tp.params.target_r_multiple: [0.75, 1.25, 1.75]
```

Retained: entry module, weekday/direction map, signal time, timeframe, data window, costs, fill assumptions, stage gates, and prop rules.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_day_of_week_seasonality/monday_open_weekend_short_0935/rescue1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.

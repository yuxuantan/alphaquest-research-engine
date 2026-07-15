# or60_signed_trend_breakout_1200

Campaign: `es_opening_range_trend_orderflow_breakout`

## Mechanic
Build the completed first 60-minute RTH opening range, then trade the first two-sided breakout before 12:00:00 ET only if the completed 5-minute breakout bar closes beyond the range, the 30/60-minute completed-bar trend structure agrees with breakout direction, and aggregate signed-volume imbalance confirms the same direction.

## Modules
- Entry: `opening_range_trend_orderflow_breakout`
- Stop: `opening_range_edge`
- Target/exit: `fixed_r`
- Forced flatten: `15:55:00` America/New_York

## Parameter Space
Declared before testing. Total combinations: 81.

```yaml
entry.params.max_opening_range_pct_of_open: [0.0045, 0.0065, 0.009]
entry.params.min_orderflow_imbalance: [0.005, 0.02, 0.04]
sl.params.stop_offset_ticks: [0, 2, 4]
tp.params.target_r_multiple: [0.75, 1.0, 1.5]
```

## Lookahead Controls
The opening range, trend windows, and orderflow confirmation use only completed bars. Engine execution remains next-bar open.


## stop_distance_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_opening_range_trend_orderflow_breakout/or60_signed_trend_breakout_1200/run1`. Only stop distance was widened by 1.5x; entry, target/exit, data, costs, fills, sessions, and validation gates are unchanged.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_opening_range_trend_orderflow_breakout/or60_signed_trend_breakout_1200/stop_widen_rescue1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.

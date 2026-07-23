# late_morning_signed_short_ema_pullback_1200 rescue1

One allowed parameter-space/fixed-parameter rescue for `es_ema_pullback_orderflow_continuation`.

Mechanic unchanged: EMA pullback continuation confirmed by completed aggregate orderflow, next-bar execution, `sweep_extreme` stop, `fixed_r` target.

Rescue changes only:

- `pullback_tolerance_ticks`: 4 -> 3 fixed ticks
- `entry.params.min_trend_gap_ticks`: `[3, 4, 5]`
- `entry.params.min_orderflow_imbalance`: `[0.0, 0.02, 0.04]`
- `sl.params.stop_offset_ticks`: `[2, 4, 6]`
- `tp.params.target_r_multiple`: `[0.75, 1.0, 1.5]`

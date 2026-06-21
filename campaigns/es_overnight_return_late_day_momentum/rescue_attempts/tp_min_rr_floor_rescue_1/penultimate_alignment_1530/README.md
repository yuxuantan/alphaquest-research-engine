# penultimate_alignment_1530 Rescue 1

Campaign: `es_overnight_return_late_day_momentum`

This is the one allowed parameter-space/fixed-parameter rescue for the failed original variant.

## Constraint
Entry module, stop module, target module, core edge, 15:30 signal clock, timeframe, data window, costs, fill assumptions, and flatten rules are unchanged.

## Rationale
Original penultimate-alignment variant failed core; rescue tests stricter overnight and penultimate-alignment thresholds while keeping the same conditional continuation mechanic.

## Parameter Space
Declared before rescue testing. Total combinations: 81.

```yaml
entry.params.min_overnight_return_ticks:
- 8
- 12
- 16
entry.params.min_penultimate_return_ticks:
- 4
- 8
- 12
sl.params.stop_pct:
- 0.0025
- 0.004
- 0.006
tp.params.target_r_multiple:
- 0.5
- 0.75
- 1.0
```


## stop_distance_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_overnight_return_late_day_momentum/penultimate_alignment_1530/rescue1`. Only stop distance was widened by 1.5x; entry, target/exit, data, costs, fills, sessions, and validation gates are unchanged.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_overnight_return_late_day_momentum/penultimate_alignment_1530/stop_widen_rescue1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.

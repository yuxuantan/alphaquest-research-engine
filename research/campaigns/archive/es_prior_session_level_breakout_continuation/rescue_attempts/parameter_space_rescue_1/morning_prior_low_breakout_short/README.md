# morning_prior_low_breakout_short Rescue 1

Campaign: `es_prior_session_level_breakout_continuation`

This is the one allowed parameter-space rescue for the failed original variant.

## Constraint
Entry module, stop module, target module, core edge, timeframe, data window, costs, fill assumptions, and flatten rules are unchanged.

## Rationale
Original short-side prior-low breakout favored wider stops and 1.5R targets; rescue tests that broad neighborhood without changing side, window, or mechanics.

## Parameter Space
Declared before rescue testing. Total combinations: 81.

```yaml
entry.params.close_buffer_ticks:
- 0
- 1
- 2
entry.params.min_volume_ratio:
- 0.0
- 0.5
- 1.0
sl.params.stop_pct:
- 0.0025
- 0.004
- 0.006
tp.params.target_r_multiple:
- 1.0
- 1.5
- 2.0
```

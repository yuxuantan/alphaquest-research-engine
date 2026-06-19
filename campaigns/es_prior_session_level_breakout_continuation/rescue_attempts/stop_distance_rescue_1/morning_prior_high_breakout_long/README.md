# morning_prior_high_breakout_long Rescue 1

Campaign: `es_prior_session_level_breakout_continuation`

This is the one allowed parameter-space rescue for the failed original variant.

## Constraint
Entry module, stop module, target module, core edge, timeframe, data window, costs, fill assumptions, and flatten rules are unchanged.

## Rationale
Original long-side prior-high breakout nearly met the profitable-combo gate but remained low-trade-count; rescue tests stricter close buffers and a cost-aware R neighborhood, with no new filter.

## Parameter Space
Declared before rescue testing. Total combinations: 81.

```yaml
entry.params.close_buffer_ticks:
- 1
- 2
- 3
entry.params.min_volume_ratio:
- 0.0
- 0.5
- 1.0
sl.params.stop_pct:
- 0.002
- 0.0025
- 0.0035
tp.params.target_r_multiple:
- 1.25
- 1.5
- 1.75
```


## stop_distance_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_prior_session_level_breakout_continuation/morning_prior_high_breakout_long/rescue1`. Only stop distance was widened by 1.5x; entry, target/exit, data, costs, fills, sessions, and validation gates are unchanged.

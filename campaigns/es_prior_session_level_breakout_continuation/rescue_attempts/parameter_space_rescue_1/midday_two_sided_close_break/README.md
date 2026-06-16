# midday_two_sided_close_break Rescue 1

Campaign: `es_prior_session_level_breakout_continuation`

This is the one allowed parameter-space rescue for the failed original variant.

## Constraint
Entry module, stop module, target module, core edge, timeframe, data window, costs, fill assumptions, and flatten rules are unchanged.

## Rationale
Original midday close-break grid had sparse but positive pockets; rescue keeps the same midday window and tests a cost-aware stop/target neighborhood without adding filters.

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
- 0.002
- 0.0025
- 0.0035
tp.params.target_r_multiple:
- 1.25
- 1.5
- 1.75
```

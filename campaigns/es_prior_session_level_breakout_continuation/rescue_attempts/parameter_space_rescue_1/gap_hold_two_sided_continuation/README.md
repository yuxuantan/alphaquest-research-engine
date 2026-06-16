# gap_hold_two_sided_continuation Rescue 1

Campaign: `es_prior_session_level_breakout_continuation`

This is the one allowed parameter-space rescue for the failed original variant.

## Constraint
Entry module, stop module, target module, core edge, timeframe, data window, costs, fill assumptions, and flatten rules are unchanged.

## Rationale
Original grid showed small outside gaps were too noisy; rescue tests only larger prior-level gaps and longer holds while keeping the gap-hold continuation mechanic.

## Parameter Space
Declared before rescue testing. Total combinations: 81.

```yaml
entry.params.min_gap_points:
- 1.5
- 2.0
- 2.5
entry.params.gap_hold_bars:
- 2
- 3
- 4
sl.params.stop_pct:
- 0.0025
- 0.004
- 0.006
tp.params.target_r_multiple:
- 1.0
- 1.5
- 2.0
```

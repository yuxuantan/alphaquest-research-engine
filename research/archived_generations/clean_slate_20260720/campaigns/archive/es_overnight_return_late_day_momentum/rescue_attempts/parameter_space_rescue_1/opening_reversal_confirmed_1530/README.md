# opening_reversal_confirmed_1530 Rescue 1

Campaign: `es_overnight_return_late_day_momentum`

This is the one allowed parameter-space/fixed-parameter rescue for the failed original variant.

## Constraint
Entry module, stop module, target module, core edge, 15:30 signal clock, timeframe, data window, costs, fill assumptions, and flatten rules are unchanged.

## Rationale
Original opening-reversal-conditioned variant failed core; rescue tests stricter overnight and opening-reversal thresholds while keeping the same conditional continuation mechanic.

## Parameter Space
Declared before rescue testing. Total combinations: 81.

```yaml
entry.params.min_overnight_return_ticks:
- 8
- 12
- 16
entry.params.min_opening_reversal_ticks:
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

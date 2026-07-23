# opening_reversal_confirmed_1530

Campaign: `es_overnight_return_late_day_momentum`

## Mechanic
At the completed 15:25-15:30 ET bar, enter in the overnight-return direction only if the first RTH window moved against the overnight return by at least the reversal threshold; flatten at 15:55 ET unless stop or target is hit.

## Modules
- Entry: `overnight_return_late_day_momentum`
- Stop: `percent_from_entry`
- Target/exit: `fixed_r`
- Forced flatten: `15:55:00` America/New_York

## Parameter Space
Declared before testing. Total combinations: 27.

```yaml
entry.params.min_overnight_return_ticks:
- 4
- 8
- 12
entry.params.min_opening_reversal_ticks:
- 2
- 4
- 8
sl.params.stop_pct:
- 0.0015
- 0.0025
- 0.004
tp.params.target_r_multiple:
- 0.75
- 1.0
- 1.5
```

## Lookahead Controls
Prior RTH close, RTH open, first-window return, and penultimate-window return are known before the completed 15:30 ET signal. Entry is next-bar open.

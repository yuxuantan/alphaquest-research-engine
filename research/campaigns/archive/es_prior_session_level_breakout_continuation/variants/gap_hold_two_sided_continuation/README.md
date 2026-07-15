# gap_hold_two_sided_continuation

Campaign: `es_prior_session_level_breakout_continuation`

## Mechanic
From the RTH open through 10:30 ET, enter with a prior-high/low outside gap only after completed 5-minute bars hold beyond the broken prior RTH level; flatten at 15:55 ET unless stop or target is hit.

## Modules
- Entry: `pdh_pdl_breakout_continuation`
- Stop: `percent_from_entry`
- Target/exit: `fixed_r`
- Forced flatten: `15:55:00` America/New_York

## Parameter Space
Declared before testing. Total combinations: 81.

```yaml
entry.params.min_gap_points:
- 0.5
- 1.0
- 2.0
entry.params.gap_hold_bars:
- 1
- 2
- 3
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
Prior RTH high/low are completed-session levels. Signals use completed 5-minute closes or completed hold bars and the engine enters at the next bar open. No archived result was used to choose this parameter space.

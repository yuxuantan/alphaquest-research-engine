# retest_hold_two_sided_breakout

Campaign: `es_prior_session_level_breakout_continuation`

## Mechanic
From 09:35 through 13:30 ET, record a fresh completed break beyond the prior RTH high/low, then enter only if a later completed retest holds outside that level; flatten at 15:55 ET unless stop or target is hit.

## Modules
- Entry: `pdh_pdl_breakout_continuation`
- Stop: `percent_from_entry`
- Target/exit: `fixed_r`
- Forced flatten: `15:55:00` America/New_York

## Parameter Space
Declared before testing. Total combinations: 81.

```yaml
entry.params.close_buffer_ticks:
- 0
- 1
- 2
entry.params.retest_window_bars:
- 1
- 3
- 5
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

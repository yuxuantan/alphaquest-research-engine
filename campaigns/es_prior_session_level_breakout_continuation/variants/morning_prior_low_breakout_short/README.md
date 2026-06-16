# morning_prior_low_breakout_short

Campaign: `es_prior_session_level_breakout_continuation`

## Mechanic
From 09:35 through 11:30 ET, enter short after a completed 5-minute bar freshly breaks and closes below the prior RTH low; flatten at 15:55 ET unless stop or target is hit.

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
entry.params.min_volume_ratio:
- 0.0
- 0.75
- 1.25
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

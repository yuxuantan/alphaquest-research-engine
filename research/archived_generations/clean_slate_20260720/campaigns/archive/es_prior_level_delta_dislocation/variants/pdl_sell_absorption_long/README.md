# pdl_sell_absorption_long

Campaign: `es_prior_level_delta_dislocation`

## Mechanic
From 10:30 through 15:30 ET, enter long when price is freshly below the prior RTH low while the completed rolling 60-minute price return is positive and signed trade flow is negative; flatten at 15:55 ET unless stop or target is hit.

## Modules
- Entry: `positive_delta_dislocation`
- Stop: `percent_from_entry`
- Target/exit: `fixed_r`
- Forced flatten: `15:55:00` America/New_York

## Parameter Space
Declared before testing. Total combinations: 81.

```yaml
entry.params.min_close_above_prev_high_ticks:
- 1
- 2
- 4
entry.params.min_hour_delta:
- 250
- 750
- 1500
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
Prior RTH high/low are completed-session levels. The 60-minute return and signed-volume fields use completed 1-minute bars ending at the signal bar close, and the engine enters at the next bar open. Archived tests are ignored for duplicate-edge checks and are not used for tuning.

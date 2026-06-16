# late_30m_absorption_fade_1500

Campaign: `es_orderflow_absorption_exhaustion_reversal`

## Mechanic
At 15:00 ET, use the completed rolling 30-minute orderflow window. If same-clock signed-flow rank is extreme and effort-vs-result rank is high but absolute return is small, fade the flow direction at the next 1-minute bar open; flatten at 15:45 ET unless stop or target is hit.

## Modules
- Entry: `orderflow_regime` (`absorption_exhaustion_reversal`)
- Stop: `percent_from_entry`
- Target/exit: `fixed_r`
- Forced flatten: `15:45:00` America/New_York

## Parameter Space
Declared before testing. Total combinations: 81.

```yaml
entry.params.pressure_rank_threshold:
- 0.8
- 0.85
- 0.9
entry.params.max_abs_return_ticks:
- 1
- 2
- 4
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
Rolling orderflow features use completed 1-minute bars only. Same-clock ranks use prior observations at the same time of day, and the engine enters at the next bar open after the completed signal bar. Archived tests are ignored for duplicate-edge checks and are not used for tuning.

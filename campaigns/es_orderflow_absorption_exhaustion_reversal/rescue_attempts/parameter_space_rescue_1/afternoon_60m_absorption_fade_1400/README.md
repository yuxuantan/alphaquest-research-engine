# afternoon_60m_absorption_fade_1400 rescue1

Campaign: `es_orderflow_absorption_exhaustion_reversal`

This is the single allowed rescue for `afternoon_60m_absorption_fade_1400`. It keeps the same `orderflow_regime` absorption/exhaustion reversal entry module, `percent_from_entry` stop module, `fixed_r` target module, 1-minute timeframe, Sierra RTH data window, costs, fills, and validation gates.

## Rescue Change Scope
Changed only fixed parameters and declared parameter space inside existing modules:

- pressure-rank threshold grid shifted to `[0.75, 0.8, 0.85]`
- effort-rank threshold made the second entry tunable: `[0.7, 0.8, 0.9]`
- `max_abs_return_ticks` fixed at `2`
- stop/target grid tightened

## Parameter Space
Declared before testing rescue1. Total combinations: 81.

```yaml
entry.params.pressure_rank_threshold:
- 0.75
- 0.8
- 0.85
entry.params.effort_rank_threshold:
- 0.7
- 0.8
- 0.9
sl.params.stop_pct:
- 0.001
- 0.0015
- 0.0025
tp.params.target_r_multiple:
- 0.5
- 0.75
- 1.0
```

No entry module, stop module, target module, edge thesis, timeframe, data window, cost model, fill model, or validation gate is changed.

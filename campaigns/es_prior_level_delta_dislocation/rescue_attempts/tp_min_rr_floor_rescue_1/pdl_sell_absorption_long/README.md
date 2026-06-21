# pdl_sell_absorption_long rescue1

Campaign: `es_prior_level_delta_dislocation`

This is the single allowed rescue for `pdl_sell_absorption_long`. It keeps the same `positive_delta_dislocation` entry module, `percent_from_entry` stop module, `fixed_r` target module, 1-minute timeframe, Sierra RTH data window, costs, fill assumptions, and validation gates.

## Rescue Change Scope
The original fixed fresh-level requirement produced zero trades because the first breach of a prior RTH level had to coincide with a completed 60-minute signal boundary. This rescue changes only fixed parameters and declared parameter space inside the same modules:

- `require_fresh_prev_high: false`
- `require_fresh_prev_low: false`
- `max_close_above_prev_high_ticks: 32`
- parameter grid changed as declared below

## Parameter Space
Declared before testing rescue1. Total combinations: 81.

```yaml
entry.params.min_close_above_prev_high_ticks:
- 0
- 1
- 2
entry.params.min_hour_delta:
- 0
- 250
- 750
sl.params.stop_pct:
- 0.001
- 0.0015
- 0.0025
tp.params.target_r_multiple:
- 0.5
- 0.75
- 1.0
```

No entry module, stop module, target module, economic edge, timeframe, data window, cost model, fill model, or validation gate is changed.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_prior_level_delta_dislocation/pdl_sell_absorption_long/rescue1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.

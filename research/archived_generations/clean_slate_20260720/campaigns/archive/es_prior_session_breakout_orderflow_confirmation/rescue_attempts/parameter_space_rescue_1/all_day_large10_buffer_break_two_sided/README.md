# all_day_large10_buffer_break_two_sided rescue1

Campaign: `es_prior_session_breakout_orderflow_confirmation`

Rescue: `parameter_space_rescue_1`

## Scope
Parameter-space/fixed-parameter rescue only. Entry, stop, target modules, edge thesis, data, costs, fills, session logic, and validation gates are unchanged.

## Rationale
Original positive rows with a 1-tick buffer fell just below 50 trades/year; rescue fixes zero buffer to preserve density and tests stop/target space around the only economically plausible 1.5R region without changing the breakout plus large10-flow mechanic.

## Parameter Space
Declared before rescue testing. Total combinations: 36.

```yaml
entry.params.min_orderflow_imbalance: [0.0, 0.001, 0.005, 0.01]
sl.params.stop_pct: [0.002, 0.0025, 0.003]
tp.params.target_r_multiple: [1.25, 1.5, 2.0]
```

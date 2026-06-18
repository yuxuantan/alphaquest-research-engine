# all_day_large20_no_buffer_break_two_sided rescue1

Campaign: `es_prior_session_breakout_orderflow_confirmation`

Rescue: `parameter_space_rescue_1`

## Scope
Parameter-space/fixed-parameter rescue only. Entry, stop, target modules, edge thesis, data, costs, fills, session logic, and validation gates are unchanged.

## Rationale
Original large20 rows were near flat but not profitable; rescue preserves no-buffer large20 confirmation and tests whether a wider predeclared stop/target region is required for the stricter participation proxy.

## Parameter Space
Declared before rescue testing. Total combinations: 36.

```yaml
entry.params.min_orderflow_imbalance: [0.0, 0.001, 0.005, 0.01]
sl.params.stop_pct: [0.003, 0.004, 0.005]
tp.params.target_r_multiple: [1.25, 1.5, 2.0]
```

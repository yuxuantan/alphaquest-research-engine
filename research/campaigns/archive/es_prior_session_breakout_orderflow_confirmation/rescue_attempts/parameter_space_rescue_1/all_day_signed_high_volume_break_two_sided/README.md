# all_day_signed_high_volume_break_two_sided rescue1

Campaign: `es_prior_session_breakout_orderflow_confirmation`

Rescue: `parameter_space_rescue_1`

## Scope
Parameter-space/fixed-parameter rescue only. Entry, stop, target modules, edge thesis, data, costs, fills, session logic, and validation gates are unchanged.

## Rationale
Original high-volume rows were close to flat only at higher volume ratios; rescue keeps the same volume-plus-signed-flow mechanic and removes the low-volume corner while testing a wider risk/reward region.

## Parameter Space
Declared before rescue testing. Total combinations: 54.

```yaml
entry.params.min_volume_ratio: [0.75, 1.0]
entry.params.min_orderflow_imbalance: [0.0, 0.005, 0.01]
sl.params.stop_pct: [0.003, 0.004, 0.005]
tp.params.target_r_multiple: [1.25, 1.5, 2.0]
```

# first_half_signed_no_buffer_break_two_sided rescue1

Campaign: `es_prior_session_breakout_orderflow_confirmation`

Rescue: `parameter_space_rescue_1`

## Scope
Parameter-space/fixed-parameter rescue only. Entry, stop, target modules, edge thesis, data, costs, fills, session logic, and validation gates are unchanged.

## Rationale
Original first-half rows had the strongest top metrics but failed parameter robustness; rescue preserves no-buffer first-half signed-flow confirmation and tests neighboring stop/target values around the plausible 1.5R region.

## Parameter Space
Declared before rescue testing. Total combinations: 36.

```yaml
entry.params.min_orderflow_imbalance: [0.0, 0.005, 0.01, 0.02]
sl.params.stop_pct: [0.002, 0.0025, 0.003]
tp.params.target_r_multiple: [1.25, 1.5, 2.0]
```

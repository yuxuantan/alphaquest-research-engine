# extreme_toxicity_positive_ret_long_1330 Rescue 1

Campaign: `es_vpin_toxicity_continuation`

This is the one allowed parameter-space/fixed-parameter rescue for the failed original variant.

## Constraint
Entry module, stop module, target module, core edge, 13:30 signal clock, timeframe, data window, costs, fill assumptions, and flatten rules are unchanged.

## Rationale
Original extreme-toxicity grid failed core; rescue tests the neighboring upper-middle toxicity tail without changing the positive-return continuation thesis.

## Parameter Space
Declared before rescue testing. Total combinations: 81.

```yaml
entry.params.vpin_rank_cutoff:
- 0.55
- 0.65
- 0.75
entry.params.min_session_return:
- 0.0
- 0.00025
- 0.0005
sl.params.stop_pct:
- 0.0015
- 0.0025
- 0.0035
tp.params.target_r_multiple:
- 1.0
- 1.5
- 2.0
```

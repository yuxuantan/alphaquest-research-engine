# retest_hold_two_sided_breakout Rescue 1

Campaign: `es_prior_session_level_breakout_continuation`

This is the one allowed parameter-space rescue for the failed original variant.

## Constraint
Entry module, stop module, target module, core edge, timeframe, data window, costs, fill assumptions, and flatten rules are unchanged.

## Rationale
Original retest-hold grid was too restrictive; rescue allows a slightly wider fixed retest tolerance and tests longer retest windows while preserving the retest-hold mechanic.

## Parameter Space
Declared before rescue testing. Total combinations: 81.

```yaml
entry.params.close_buffer_ticks:
- 1
- 2
- 3
entry.params.retest_window_bars:
- 3
- 5
- 7
sl.params.stop_pct:
- 0.0025
- 0.004
- 0.006
tp.params.target_r_multiple:
- 1.0
- 1.5
- 2.0
```

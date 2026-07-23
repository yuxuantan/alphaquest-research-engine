# prior_close_morning_signed_reclaim_reversion_1130

Morning two-sided failed probe of the completed previous RTH close with total signed-volume counterflow confirmation.

Entry uses completed previous RTH benchmark levels and completed signed_volume counterflow only. Stops use the completed signal-bar sweep extreme plus a tick offset; targets use fixed R; positions flatten at 12:30:00 ET.

## Rescue Attempt 1

This is a parameter-space/fixed-parameter rescue only. It preserves the prior-session benchmark open/close probe-and-reclaim/reject entry module, sweep-extreme stop module, fixed-R target module, timeframe, data, costs, fills, sessions, prop rules, and staged validation gates. The rescue grid is:

- `entry.params.min_probe_ticks`: `[1, 2, 3]`
- `entry.params.min_orderflow_imbalance`: `[0.02, 0.04, 0.06]`
- `sl.params.stop_offset_ticks`: `[1, 2, 3]`
- `tp.params.target_r_multiple`: `[1.0, 1.5, 2.0]`

Total combinations: `81`.

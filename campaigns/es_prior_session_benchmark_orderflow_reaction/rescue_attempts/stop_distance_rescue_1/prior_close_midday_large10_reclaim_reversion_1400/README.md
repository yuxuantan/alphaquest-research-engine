# prior_close_midday_large10_reclaim_reversion_1400

Midday failed probe of the previous RTH close requiring large-10 trade-size counterflow on the reclaim/rejection bar.

Entry uses completed previous RTH benchmark levels and completed large10 counterflow only. Stops use the completed signal-bar sweep extreme plus a tick offset; targets use fixed R; positions flatten at 15:00:00 ET.

## Rescue Attempt 1

This is a parameter-space/fixed-parameter rescue only. It preserves the prior-session benchmark open/close probe-and-reclaim/reject entry module, sweep-extreme stop module, fixed-R target module, timeframe, data, costs, fills, sessions, prop rules, and staged validation gates. The rescue grid is:

- `entry.params.min_probe_ticks`: `[1, 2, 3]`
- `entry.params.min_orderflow_imbalance`: `[0.02, 0.04, 0.06]`
- `sl.params.stop_offset_ticks`: `[1, 2, 3]`
- `tp.params.target_r_multiple`: `[1.0, 1.5, 2.0]`

Total combinations: `81`.


## stop_distance_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_prior_session_benchmark_orderflow_reaction/prior_close_midday_large10_reclaim_reversion_1400/rescue1`. Only stop distance was widened by 1.5x; entry, target/exit, data, costs, fills, sessions, and validation gates are unchanged.

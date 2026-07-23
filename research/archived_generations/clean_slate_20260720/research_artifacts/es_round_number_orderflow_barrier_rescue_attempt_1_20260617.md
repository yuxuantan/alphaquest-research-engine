# ES Round-Number Orderflow Barrier Rescue Attempt 1

Date: 2026-06-17

Scope: one parameter-space-only rescue per failed original variant in
`es_round_number_orderflow_barrier`.

Original result before rescue: all five original variants failed
`limited_core_grid_test`. No original reached monkey, WFA, Monte Carlo,
simulated incubation, frozen validation, or candidate reporting.

Allowed rescue changes:

- `test_run_id` changed from `run1` to `rescue1`.
- Absorption variants changed only `entry.params.min_orderflow_imbalance`,
  `sl.params.stop_pct`, `tp.params.target_r_multiple`, and matching default
  values.
- Breakout variants changed only `entry.params.barrier_interval_points`,
  `entry.params.min_orderflow_imbalance`, `sl.params.stop_pct`,
  `tp.params.target_r_multiple`, and matching default values.

Forbidden and unchanged:

- Edge thesis
- Entry module
- Stop module
- Target module
- Setup mode
- Flow confirmation logic
- Flow mode
- Timeframe
- Data source and data window
- Commission, slippage, tick size, point value
- Session and forced-flatten rules
- Stage criteria

Original failure observations used only to choose the predeclared rescue lane:

- Morning absorption variants had some profitable rows but weak limited-window
  trade density and failed the 70% profitable-combination gate.
- Midday large10 absorption had enough density but almost no profitable
  combinations.
- Downside breakout produced a few benchmark-passing rows but failed grid
  stability.
- Upside breakout failed grid stability and density in part of the limited
  window.

Rescue parameter space:

- Absorption variants:
  - `entry.params.buffer_ticks`: `[0, 1]`
  - `entry.params.min_orderflow_imbalance`: `[0.005, 0.02, 0.04]`
  - `sl.params.stop_pct`: `[0.001, 0.002, 0.0035]`
  - `tp.params.target_r_multiple`: `[1.25, 2.0, 3.0]`
- Breakout variants:
  - `entry.params.barrier_interval_points`: `[10.0, 25.0, 50.0]`
  - `entry.params.min_orderflow_imbalance`: `[0.005, 0.02, 0.04]`
  - `sl.params.stop_pct`: `[0.001, 0.002, 0.0035]`
  - `tp.params.target_r_multiple`: `[1.25, 2.0, 3.0]`

Pre-result decision: approve rescue for testing under the user rule that each
failed variant can receive exactly one rescue run, limited to parameter space or
fixed-parameter changes without changing core mechanics.

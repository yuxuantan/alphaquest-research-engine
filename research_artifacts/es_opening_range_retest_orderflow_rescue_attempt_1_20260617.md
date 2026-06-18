# ES Opening-Range Retest Orderflow Rescue Attempt 1

Date: 2026-06-17

Scope: one parameter-space-only rescue per failed original variant in
`es_opening_range_retest_orderflow`.

Original result before rescue: all five original variants failed
`limited_core_grid_test`. Every original grid had adequate signal and trade
density in the limited core window, but every variant had `0.0` profitable-combo
rate after ES costs.

Allowed rescue changes:

- `test_run_id` changed from `run1` to `rescue1`.
- Entry parameter space changed only for existing `max_retest_bars` and
  `min_orderflow_imbalance`.
- Stop parameter space changed only for existing `stop_offset_ticks`.
- Target parameter space changed only for existing `target_r_multiple`.
- Matching fixed defaults were changed inside the same existing modules.

Forbidden and unchanged:

- Edge thesis
- Entry module
- Stop module
- Target module
- Opening-range break-and-retest mechanic
- Flow mode
- Flow confirmation mode
- Timeframe
- Data source and data window
- Commission, slippage, tick size, point value
- Session and forced-flatten rules
- Validation gates

Rescue parameter space:

- `entry.params.max_retest_bars`: `[1, 2, 3]`
- `entry.params.min_orderflow_imbalance`:
  - signed-flow variants: `[0.0, 0.01, 0.03]`
  - large-flow variants: `[0.0, 0.02, 0.05]`
- `sl.params.stop_offset_ticks`: `[6, 10, 14]`
- `tp.params.target_r_multiple`: `[0.5, 0.75, 1.0]`

Rationale before results: the originals failed with adequate event density but
negative PnL across the grid. The only plausible non-mechanic rescue is to test
whether the boundary stop was too tight for realistic next-bar ES fills and
whether smaller fixed-R exits are required for a retest/bounce mechanic. The
rescue does not add filters or change the economic edge.

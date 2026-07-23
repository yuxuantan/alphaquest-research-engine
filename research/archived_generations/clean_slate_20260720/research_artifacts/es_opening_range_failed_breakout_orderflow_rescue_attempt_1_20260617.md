# ES opening-range failed breakout orderflow rescue attempt 1 - 2026-06-17

Scope: one rescue per failed original variant. All five originals failed `limited_core_grid_test` with `0.0` profitable-combo rate, but none were zero-signal failures.

Allowed rescue change:

- Keep `entry.module: opening_range_failed_breakout_orderflow`.
- Keep `sl.module: opening_range_edge`.
- Keep `tp.module: opening_range_opposite_edge`.
- Keep data, costs, fills, sessions, prop rules, timeframe, and staged benchmarks unchanged.
- Change only the stop-offset fixed/default value and `sl.params.stop_offset_ticks` parameter space from the original `[0, 2, 4]` to rescue `[4, 8, 12]`.
- Keep the same core mechanic: opening-range failed breakout, reclaim through the same boundary, opposite aggregate orderflow, and target at the opposite opening-range edge.

Rationale: the best original rows consistently selected the largest available stop offset (`4` ticks), suggesting the original range-edge stop may have been too tight for normal reclaim noise. This is a parameter-space rescue, not a new strategy mechanic.

Status: completed_failed. All five rescue runs failed `limited_core_grid_test`. Best rescue was `or60_signed_failed_reclaim_1200/rescue1` with top net `-1037.5`, PF `0.9226179377214245`, and `0.0` profitable-combo rate.

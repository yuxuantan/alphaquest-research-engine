# ES Wide-Range Orderflow Continuation Rescue Attempt 1 - 2026-06-18

Scope: one parameter-space-only rescue for each of the five original variants after all originals failed limited core.

Unchanged:
- entry module: `wide_range_orderflow_continuation`
- stop module: `percent_from_entry`
- target module: `fixed_r`
- data source, timeframe, costs, session rules, next-bar execution, pessimistic same-bar handling, and stage criteria
- core mechanic: completed wide-range directional bar closing near the extreme plus aligned completed aggregate orderflow

Changed:
- `entry.params.min_range_ticks` to `[10, 12]` for all variants
- `entry.params.min_orderflow_imbalance` to adjacent density-safe values per variant
- `sl.params.stop_pct` to wider adjacent values after original top rows clustered at the widest stop
- `tp.params.target_r_multiple` to adjacent values by variant side/session

Density guard: `[12, 16]` was rejected before rescue testing because the strict afternoon large-20 corners fell below 50 trades/year in the limited-core random window. `[10, 12]` keeps the rescue inside the same mechanic while preserving event frequency.

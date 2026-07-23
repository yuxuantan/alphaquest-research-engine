# ES session open orderflow reclaim rescue attempt 1 - 2026-06-18

Scope: one allowed parameter-space-only rescue for each failed variant in `es_session_open_orderflow_reclaim`.

Original result:

- All five original variants failed `limited_core_grid_test`.
- No original reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation.
- Failure was not a density issue: the pre-PnL density audit showed all five variants cleared the 50 trades/year feasibility floor at declared entry-grid corners.

Allowed rescue changes:

- Keep entry module: `session_open_orderflow_reclaim`.
- Keep stop module: `percent_from_entry`.
- Keep target module: `fixed_r`.
- Keep symbol, timeframe, data window, costs, session logic, prop rules, and staged gates unchanged.
- Change only fixed parameters inside existing modules and tunable parameter space.

Rescue parameter space:

- `entry.params.min_open_extension_ticks`: `[8, 10, 12]`
- `entry.params.min_orderflow_imbalance`: `[0.30, 0.40, 0.50]`
- `sl.params.stop_pct`: `[0.0025, 0.004, 0.006]`
- `tp.params.target_r_multiple`: `[1.0, 1.5, 2.0]`

Rationale before rescue results:

- The original grids were broadly negative, so the rescue tested whether stricter open-extension and stronger orderflow confirmation were needed to isolate real trapped-inventory events.
- Wider stop/target geometry tested whether open-reclaim pressure needs room to resolve rather than tight same-session stop-outs.
- No new filter, time window, data source, direction rule, or strategy module was added.

Rescue results:

| Variant | Profitable combo rate | Benchmark-pass combos | Top net | Top PF | Top trades/year |
|---|---:|---:|---:|---:|---:|
| `afternoon_large20_down_open_reclaim_long` | 0.0000 | 0 | -2437.50 | 0.8867 | 127.42 |
| `afternoon_large20_up_open_reject_short` | 0.0123 | 0 | 32.50 | 1.0018 | 91.79 |
| `midday_large10_two_sided_open_reclaim` | 0.0000 | 0 | -2352.50 | 0.9290 | 151.66 |
| `morning_down_open_reclaim_long` | 0.0494 | 1 | 0.00 | 1.0000 | 74.86 |
| `morning_up_open_reject_short` | 0.0988 | 2 | 1572.50 | 1.1077 | 89.85 |

Decision after rescue: FAIL. All rescues failed `limited_core_grid_test`; no candidate report was created.

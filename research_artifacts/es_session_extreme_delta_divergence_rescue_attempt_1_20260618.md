# ES Session-Extreme Cumulative-Delta Divergence Rescue Attempt 1 - 2026-06-18

Trigger: all five original variants failed `limited_core_grid_test` with `0.0` profitable combinations.

Scope: per failed variant, exactly one rescue each.

Allowed changes used:
- changed fixed `entry.params.close_reclaim_tolerance_ticks` inside the existing `session_extreme_delta_divergence` module;
- changed declared `entry.params.min_extreme_break_ticks` grid inside the same module;
- kept `entry.params.max_delta_progress_ratio` as `[0.05, 0.1]`;
- shifted only the existing `sl.params.stop_pct` grid wider to `[0.0025, 0.004, 0.006]`;
- kept target module and target grid unchanged.

Forbidden changes not made:
- no entry, stop, or target module change;
- no direction flip from fade to continuation;
- no new filter, data source, timeframe, session window, cost, fill, benchmark, or validation-gate change;
- no paid data or external download.

Rationale: the original grid was dense but too broad; all top rows preferred the larger declared fresh break and/or larger stop. The rescue makes the same edge cleaner by avoiding 1-tick probes and requiring the close to remain nearer to the prior completed session extreme.

Pre-rescue density check, before rescue PnL:

| variant | rescue break grid | close tolerance ticks | shortlist min signals/year | WFA min signals/year |
|---|---:|---:|---:|---:|
| `morning_high_delta_divergence_short` | `[2, 3]` | 4 | 57.2 | 95.9 |
| `morning_low_delta_divergence_long` | `[2, 3]` | 4 | 63.7 | 97.0 |
| `midday_two_sided_delta_divergence` | `[2, 3]` | 4 | 92.9 | 138.0 |
| `afternoon_high_delta_divergence_short` | `[2]` | 8 | 63.0 | 75.8 |
| `afternoon_low_delta_divergence_long` | `[2]` | 8 | 54.6 | 67.0 |

Decision: approve the one-time rescue runs for staged testing. If these fail, the campaign is rejected; no second rescue is allowed.

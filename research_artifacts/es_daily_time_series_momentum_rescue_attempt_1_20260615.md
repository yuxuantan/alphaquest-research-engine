# ES Daily Time-Series Momentum Rescue Audit

Date: 2026-06-15

Decision: FAIL

## Scope

Campaign: `es_daily_time_series_momentum`

This campaign tested a newly active ES daily time-series momentum edge using
prior completed RTH closes from the corrected Sierra 1-minute RTH OHLCV/orderflow
cache aggregated to 5-minute strategy bars. Archived tests were ignored for
duplicate-edge blocking. The active duplicate gate did not contain this edge.

Each original variant had exactly 81 combinations: two entry tunables, one stop
tunable, and one target tunable. After all five originals failed, each failed
variant received one parameter-space-only rescue. No rescue changed the prior
daily-trend edge, entry module, direction policy, signal time, flatten time,
timeframe, data source, costs, fill assumptions, or validation gates.

## Results

| Variant | Run | Terminal stage | Core pct | Top net | Top PF | Top MAR | Top trades | Decision |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `long_only_trend_1000` | `run1` | `limited_core_grid_test` | 0.0 | -572.5 | 0.9722894482090997 | -0.16400829711174925 | 142 | FAIL |
| `long_only_trend_1000` | `rescue1` | `limited_core_grid_test` | 0.2839506172839506 | 2822.5 | 1.1703636637996078 | 1.610401778121528 | 123 | FAIL |
| `short_term_alignment_1000_two_sided` | `run1` | `limited_core_grid_test` | 0.0 | -6951.25 | 0.7417572211386645 | -0.8988220875006913 | 239 | FAIL |
| `short_term_alignment_1000_two_sided` | `rescue1` | `limited_core_grid_test` | 0.0 | -3692.5 | 0.5051926298157454 | -1.2447049341268945 | 121 | FAIL |
| `sixty_day_trend_1000_two_sided` | `run1` | `limited_core_grid_test` | 0.0 | -6626.25 | 0.7781822746673361 | -0.7520711549246879 | 269 | FAIL |
| `sixty_day_trend_1000_two_sided` | `rescue1` | `limited_core_grid_test` | 0.19753086419753085 | 2822.5 | 1.1703636637996078 | 1.610401778121528 | 123 | FAIL |
| `twenty_day_trend_1000_two_sided` | `run1` | `limited_core_grid_test` | 0.0 | -7438.75 | 0.776781695423856 | -0.726581091785469 | 299 | FAIL |
| `twenty_day_trend_1000_two_sided` | `rescue1` | `limited_core_grid_test` | 0.0 | -7776.25 | 0.8003786420228469 | -0.5708971932978288 | 354 | FAIL |
| `vol_norm_trend_1000_two_sided` | `run1` | `limited_core_grid_test` | 0.012345679012345678 | 452.5 | 1.033920539730135 | 0.14326643386111598 | 92 | FAIL |
| `vol_norm_trend_1000_two_sided` | `rescue1` | `limited_core_grid_test` | 0.14814814814814814 | 1392.5 | 1.104542042042042 | 1.0879858221603893 | 89 | FAIL |

The strongest rescue rows were positive, but they were narrow surfaces: the
long-only rescue reached only `0.2839506172839506` profitable combinations, the
60-day two-sided rescue reached `0.19753086419753085`, and the
volatility-normalized rescue reached `0.14814814814814814`. All are below the
`0.70` core-grid requirement, so no WFA is allowed.

## Conclusion

No variant reached monkey, WFA, Monte Carlo, or frozen validation. No candidate
strategy report was created.

Final decision: FAIL.

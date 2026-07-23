# ES Daily Time-Series Momentum Campaign Summary

Decision: FAIL

All five original variants and all five one-time parameter-space-only rescues failed the limited core-grid profitable-combination gate before WFA completion.

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

No WFA, WFA monkey, Monte Carlo, or frozen validation stage was reached. No candidate strategy report was created.

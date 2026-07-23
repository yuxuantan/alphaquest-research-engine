# Campaign Test Summary

Campaign: `es_cftc_tff_hedging_pressure`

Decision: FAIL

All five corrected CFTC/TFF hedging-pressure originals failed the limited core-grid gate, and all five one-time parameter-space-only rescues also failed core. No run reached monkey, WFA, Monte Carlo, or frozen validation.

Invalidated run note: `run1` started before non-null shifted CFTC feature coverage and is not economic evidence. Valid originals are `run2`.

| Variant | Run | Terminal stage | Profitable/monkey rate | Top net | Top trades | Decision |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `broad_negative_pressure_short_1100` | `run2` | `limited_core_grid_test` | `0.0` | `0.0` | `0` | FAIL |
| `broad_negative_pressure_short_1100` | `rescue1` | `limited_core_grid_test` | `0.0` | `-1208.75` | `103` | FAIL |
| `broad_positive_pressure_long_1100` | `run2` | `limited_core_grid_test` | `0.14814814814814814` | `1100.0` | `5` | FAIL |
| `broad_positive_pressure_long_1100` | `rescue1` | `limited_core_grid_test` | `0.0` | `-2465.0` | `58` | FAIL |
| `extreme_negative_pressure_short_1330` | `run2` | `limited_core_grid_test` | `0.1111111111111111` | `262.5` | `5` | FAIL |
| `extreme_negative_pressure_short_1330` | `rescue1` | `limited_core_grid_test` | `0.18518518518518517` | `262.5` | `5` | FAIL |
| `extreme_positive_pressure_long_1330` | `run2` | `limited_core_grid_test` | `0.0` | `0.0` | `0` | FAIL |
| `extreme_positive_pressure_long_1330` | `rescue1` | `limited_core_grid_test` | `0.3333333333333333` | `775.0` | `5` | FAIL |
| `high_positive_pressure_long_0935` | `run2` | `limited_core_grid_test` | `0.0` | `0.0` | `0` | FAIL |
| `high_positive_pressure_long_0935` | `rescue1` | `limited_core_grid_test` | `0.1111111111111111` | `915.625` | `5` | FAIL |

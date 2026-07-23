# ES Turn-of-Month Seasonality Campaign Summary

Decision: FAIL

All five original variants and all five one-time parameter-space-only rescues failed the limited core-grid profitable-combination gate before WFA completion.

| Variant | Run | Terminal stage | Core/monkey pct | Top net | Top PF | Top trades | Decision |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `classic_turn_window_1000_long` | `run1` | `limited_core_grid_test` | 0.037037037037037035 | 577.5 | 1.0616987179487178 | 62 | FAIL |
| `classic_turn_window_1000_long` | `rescue1` | `limited_core_grid_test` | 0.0 | -96.25 | 0.9914501443482123 | 73 | FAIL |
| `early_month_first_days_1000_long` | `run1` | `limited_core_grid_test` | 0.0 | -287.5 | 0.8727876106194691 | 25 | FAIL |
| `early_month_first_days_1000_long` | `rescue1` | `limited_core_grid_test` | 0.07407407407407407 | 178.75 | 1.0998603351955307 | 13 | FAIL |
| `late_turn_window_1300_long` | `run1` | `limited_core_grid_test` | 0.0 | -810.0 | 0.9107192063929457 | 97 | FAIL |
| `late_turn_window_1300_long` | `rescue1` | `limited_core_grid_test` | 0.0 | -352.5 | 0.95425048669695 | 73 | FAIL |
| `month_end_last_days_1000_long` | `run1` | `limited_core_grid_test` | 0.3333333333333333 | 1991.25 | 1.3051724137931036 | 48 | FAIL |
| `month_end_last_days_1000_long` | `rescue1` | `limited_core_grid_test` | 0.0 | -206.25 | 0.9775326797385621 | 60 | FAIL |
| `opening_turn_window_0935_long` | `run1` | `limited_core_grid_test` | 0.04938271604938271 | 355.0 | 1.045939825299256 | 74 | FAIL |
| `opening_turn_window_0935_long` | `rescue1` | `limited_core_grid_test` | 0.07407407407407407 | 1685.0 | 1.247248716067498 | 73 | FAIL |

No WFA, WFA monkey, Monte Carlo, or frozen validation stage was reached. No candidate strategy report was created.

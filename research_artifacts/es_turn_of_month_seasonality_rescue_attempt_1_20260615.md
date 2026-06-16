# ES Turn-of-Month Seasonality Rescue Audit

Date: 2026-06-15

Decision: FAIL

## Scope

Campaign: `es_turn_of_month_seasonality`

This campaign tested a newly active ES calendar turn-of-month seasonality edge
using the corrected Sierra 1-minute RTH OHLCV/orderflow cache aggregated to
5-minute strategy bars. Archived turn-of-month tests were ignored for
duplicate-edge blocking, but prior archive existence was treated as historical
context only. The active duplicate gate did not contain this edge.

Each combined-window variant had exactly 81 combinations: two entry tunables
(`entry.params.first_calendar_days` and `entry.params.last_calendar_days`), one
stop tunable, and one target tunable. Each isolated early-month/month-end
variant had exactly 27 combinations. After all five originals failed, each
failed variant received one parameter-space-only rescue. No rescue changed the
calendar edge, direction, entry module, stop module, target module, signal time,
flatten time, timeframe, data source, costs, fill assumptions, or validation
gates.

## Results

| Variant | Run | Terminal stage | Core pct | Top net | Top PF | Top trades | Decision |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `classic_turn_window_1000_long` | `run1` | `limited_core_grid_test` | 0.037037037037037035 | 577.5 | 1.0616987179487178 | 62 | FAIL |
| `classic_turn_window_1000_long` | `rescue1` | `limited_core_grid_test` | 0.0 | -96.25 | 0.9914501443482123 | 73 | FAIL |
| `early_month_first_days_1000_long` | `run1` | `limited_core_grid_test` | 0.0 | -287.5 | 0.8727876106194691 | 25 | FAIL |
| `early_month_first_days_1000_long` | `rescue1` | `limited_core_grid_test` | 0.07407407407407407 | 178.75 | 1.0998603351955307 | 13 | FAIL |
| `month_end_last_days_1000_long` | `run1` | `limited_core_grid_test` | 0.3333333333333333 | 1991.25 | 1.3051724137931036 | 48 | FAIL |
| `month_end_last_days_1000_long` | `rescue1` | `limited_core_grid_test` | 0.0 | -206.25 | 0.9775326797385621 | 60 | FAIL |
| `opening_turn_window_0935_long` | `run1` | `limited_core_grid_test` | 0.04938271604938271 | 355.0 | 1.045939825299256 | 74 | FAIL |
| `opening_turn_window_0935_long` | `rescue1` | `limited_core_grid_test` | 0.07407407407407407 | 1685.0 | 1.247248716067498 | 73 | FAIL |
| `late_turn_window_1300_long` | `run1` | `limited_core_grid_test` | 0.0 | -810.0 | 0.9107192063929457 | 97 | FAIL |
| `late_turn_window_1300_long` | `rescue1` | `limited_core_grid_test` | 0.0 | -352.5 | 0.95425048669695 | 73 | FAIL |

The best-looking original row was the month-end-only variant, but the profitable
combination rate was only `0.3333333333333333` and the top row had only `48`
trades, below the methodology's required core-grid stability. The best-looking
rescue row was the opening-window rescue, but only `0.07407407407407407`
combinations were profitable, far below the `0.70` gate.

## Conclusion

No variant reached monkey, WFA, Monte Carlo, or frozen validation. No candidate
strategy report was created.

Final decision: FAIL.

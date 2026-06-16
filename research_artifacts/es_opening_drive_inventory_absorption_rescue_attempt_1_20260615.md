# ES Opening-Drive Inventory Absorption Rescue Audit

Date: 2026-06-15

Decision: FAIL

## Scope

Campaign: `es_opening_drive_inventory_absorption`

This campaign tested a newly active opening-drive inventory/absorption edge using
the corrected Sierra 1-minute RTH orderflow cache. Archived opening-drive tests
were ignored for duplicate-edge blocking, but prior instability was treated as
research context. The active duplicate gate did not contain this edge.

Each original variant had exactly 81 combinations: two entry tunables
(`entry.params.slots.0.min_open_return_ticks` and
`entry.params.slots.0.min_open_volume_rank`), one stop tunable, and one target
tunable. After all five originals failed, each failed variant received one
parameter-space-only rescue. No rescue changed the opening-drive family,
direction, entry time, flatten time, data source, costs, fill assumptions, or
validation gates.

## Results

| Variant | Run | Terminal stage | Core/monkey pct | Top net | Top PF | Top trades | One-tick stress | Decision |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| `open30_flow_continuation_1030` | `run1` | `limited_core_grid_test` | 0.38271604938271603 | 730.0 | 2.3394495412844036 | 14 |  | FAIL |
| `open30_flow_continuation_1030` | `rescue1` | `limited_core_grid_test` | 0.35802469135802467 | 791.25 | 2.276209677419355 | 13 |  | FAIL |
| `open60_flow_continuation_1130` | `run1` | `limited_monkey_test` | 0.16333333333333333 | 552.5 |  | 42 | False | FAIL |
| `open60_flow_continuation_1130` | `rescue1` | `limited_monkey_test` | 0.20666666666666667 | 587.5 |  | 25 | False | FAIL |
| `open30_absorbed_pressure_fade_1015` | `run1` | `limited_core_grid_test` | 0.0 | -432.5 | 0.45425867507886436 | 9 |  | FAIL |
| `open30_absorbed_pressure_fade_1015` | `rescue1` | `limited_core_grid_test` | 0.0 | -295.0 | 0.8262150220913107 | 24 |  | FAIL |
| `open60_exhaustion_fade_1300` | `run1` | `limited_core_grid_test` | 0.5555555555555556 | 377.5 | 1.8162162162162163 | 12 |  | FAIL |
| `open60_exhaustion_fade_1300` | `rescue1` | `limited_core_grid_test` | 0.4074074074074074 | 299.375 | 1.6472972972972972 | 12 |  | FAIL |
| `open30_price_flow_divergence_fade_1400` | `run1` | `limited_core_grid_test` | 0.0 | -202.5 | 0.22115384615384615 | 3 |  | FAIL |
| `open30_price_flow_divergence_fade_1400` | `rescue1` | `limited_core_grid_test` | 0.0 | -117.5 | 0.8715846994535519 | 21 |  | FAIL |

One `open60_flow_continuation_1130` rescue attempt initially hit a transient
process-pool error during core-grid execution. The same frozen rescue config was
rerun and completed normally; the valid terminal result is the `limited_monkey_test`
failure shown above.

## Conclusion

No variant reached WFA. No candidate strategy report was created.

Final decision: FAIL.

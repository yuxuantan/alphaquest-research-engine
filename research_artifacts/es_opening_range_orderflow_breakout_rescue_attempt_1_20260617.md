# ES Opening Range Orderflow Breakout Rescue Attempt 1 - 2026-06-17

Scope: one rescue per failed original variant.

Original result summary:

| Variant | Terminal stage | Profitable combo rate | Apex violations |
|---|---|---:|---:|
| `or15_signed_flow_breakout_1030` | `limited_core_grid_test` | 0.0000 | 0 |
| `or30_signed_flow_breakout_1100` | `limited_core_grid_test` | 0.0000 | 0 |
| `or15_large10_flow_breakout_1030` | `limited_core_grid_test` | 0.0000 | 0 |
| `or30_large20_flow_breakout_1100` | `limited_core_grid_test` | 0.0000 | 0 |
| `or60_signed_flow_breakout_1200` | `limited_core_grid_test` | 0.0741 | 0 |

Allowed rescue changes:
- Keep `entry.module: opening_range_orderflow_breakout`.
- Keep `sl.module: opening_range_edge`.
- Keep `tp.module: fixed_r`.
- Keep the same ES local Sierra data, 5-minute timeframe, RTH session, costs,
  slippage, fills, flatten rules, and validation gates.
- Change only fixed/default parameters and declared parameter grids.

Rescue parameter space:
- `entry.params.breakout_buffer_ticks`: `[0, 1, 2]`
- `entry.params.min_orderflow_imbalance`: `[0.02, 0.04, 0.06]`
- `sl.params.max_stop_points`: `[16, 24, 32]`
- `tp.params.target_r_multiple`: `[0.25, 0.5, 0.75]`

Rationale: The original variants did not show broad profitability with larger
breakout buffers and 0.75-1.5R targets. This rescue tests whether the same
price-action plus orderflow-confirmation mechanic has only short post-breakout
follow-through that must be harvested with a smaller fixed-R target. It does not
convert the setup to a fade, add a trend filter, change sessions, or change the
core edge.

Rescue configs:
- `campaigns/es_opening_range_orderflow_breakout/rescue_attempts/parameter_space_rescue_1/or15_signed_flow_breakout_1030/config.yaml`
- `campaigns/es_opening_range_orderflow_breakout/rescue_attempts/parameter_space_rescue_1/or30_signed_flow_breakout_1100/config.yaml`
- `campaigns/es_opening_range_orderflow_breakout/rescue_attempts/parameter_space_rescue_1/or15_large10_flow_breakout_1030/config.yaml`
- `campaigns/es_opening_range_orderflow_breakout/rescue_attempts/parameter_space_rescue_1/or30_large20_flow_breakout_1100/config.yaml`
- `campaigns/es_opening_range_orderflow_breakout/rescue_attempts/parameter_space_rescue_1/or60_signed_flow_breakout_1200/config.yaml`

# es_nq_semivariance_filtered_relative_value_absorption Rescue Attempt 1 Density Audit

All five original variants failed `limited_core_grid_test` despite clearing trade
density. Per the campaign rescue policy, each failed variant receives one
parameter-space/fixed-parameter rescue. No entry, stop-loss, take-profit module,
data window, cost model, fill model, or validation benchmark is changed.

## Rescue Scope

- Tighten `entry.params.benign_semivar_rank_max` from `[0.45, 0.50]` to `[0.40, 0.45]`.
- Adjust `entry.params.min_spread_bps` within the same ES/NQ divergence mechanic.
- Widen `sl.params.stop_pct` from `[0.0025, 0.004, 0.006]` to `[0.004, 0.006, 0.008]`.
- Leave `tp.params.target_r_multiple` unchanged at `[1.0, 1.5]`; no target RR below 1.0 is allowed.

## Trade-Density Check

The density check counts the first qualifying completed-bar signal per RTH
session using the same ES/NQ divergence, signed-flow absorption, and lagged
semivariance filter. It is a frequency screen only.

| variant_id | min_spread_grid | semivar_rank_grid | limited_core_min_tpy | latest1y_min_tpy | decision |
|---|---|---|---:|---:|---|
| morning15_low_badvol_absorption_twosided_1100 | `[3, 4, 5]` | `[0.40, 0.45]` | 66.29 | 78.27 | approve_rescue |
| morning30_low_badvol_absorption_twosided_1130 | `[3, 4, 5]` | `[0.40, 0.45]` | 51.99 | 61.21 | approve_rescue |
| late_morning30_low_badvol_absorption_twosided_1230 | `[2, 3, 4]` | `[0.40, 0.45]` | 61.09 | 51.18 | approve_rescue |
| midday60_low_badvol_absorption_twosided_1430 | `[4, 5, 6]` | `[0.40, 0.45]` | 53.29 | 51.18 | approve_rescue |
| midday60_low_downside_share_absorption_twosided_1430 | `[2, 3, 4]` | `[0.40, 0.45]` | 57.19 | 59.20 | approve_rescue |

Final decision: APPROVE_ONE_TIME_PARAMETER_RESCUE_FOR_ALL_FAILED_VARIANTS.

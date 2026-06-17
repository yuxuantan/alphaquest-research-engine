# ES AQR BAB Factor State Rescue Attempt 1 - 2026-06-17

Scope: one rescue per failed variant after all five originals failed before WFA.

Allowed change boundary: parameter space / fixed parameters only. No feature column, setup mode, direction, entry time, data window, cost, fill, session, prop-rule, or stage-gate changes were made.

| Variant | Threshold grid | Stop grid | Target grid | Config |
|---|---:|---:|---:|---|
| `low_bab_daily_rebound_long_0935` | [0.25, 0.275, 0.3] | [0.003, 0.004, 0.005] | [1.5, 2.0, 2.5] | `campaigns/es_aqr_bab_factor_state/rescue_attempts/parameter_space_rescue_1/low_bab_daily_rebound_long_0935/config.yaml` |
| `low_bab_21d_rebound_long_1000` | [0.25, 0.275, 0.3] | [0.003, 0.004, 0.005] | [1.5, 2.0, 2.5] | `campaigns/es_aqr_bab_factor_state/rescue_attempts/parameter_space_rescue_1/low_bab_21d_rebound_long_1000/config.yaml` |
| `low_bab_63d_rebound_long_1030` | [0.25, 0.275, 0.3] | [0.003, 0.004, 0.005] | [1.5, 2.0, 2.5] | `campaigns/es_aqr_bab_factor_state/rescue_attempts/parameter_space_rescue_1/low_bab_63d_rebound_long_1030/config.yaml` |
| `low_bab_z63_rebound_long_1100` | [0.25, 0.275, 0.3] | [0.003, 0.004, 0.005] | [1.5, 2.0, 2.5] | `campaigns/es_aqr_bab_factor_state/rescue_attempts/parameter_space_rescue_1/low_bab_z63_rebound_long_1100/config.yaml` |
| `bab_63d_extreme_two_sided_1330` | [0.1, 0.125, 0.15] | [0.003, 0.004, 0.005] | [1.5, 2.0, 2.5] | `campaigns/es_aqr_bab_factor_state/rescue_attempts/parameter_space_rescue_1/bab_63d_extreme_two_sided_1330/config.yaml` |

Decision before rescue testing: proceed to preflight and staged testing. Results cannot alter mechanics.

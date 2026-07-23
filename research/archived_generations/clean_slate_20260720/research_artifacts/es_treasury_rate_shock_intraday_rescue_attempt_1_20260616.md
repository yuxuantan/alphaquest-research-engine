# ES Treasury Rate Shock Intraday Rescue Attempt 1 - 2026-06-16

Decision: FAIL.

Scope: one rescue per failed variant. Rescues changed only declared threshold, stop, and target parameter spaces inside the existing `treasury_rate_state`, `percent_from_entry`, and `fixed_r` modules. Signal clock, setup mode, direction, feature construction, timeframe, data window, costs, fill assumptions, prop-rule gates, and staged validation gates were unchanged.

Feature file: `data/external/es_treasury_rate_state_features_20110103_20260609.csv`.

Density audit: `research_artifacts/es_treasury_rate_shock_intraday_density_audit_20260616.md`.

No paid data was used.

| Variant | Original profitable-combo rate | Rescue profitable-combo rate | Terminal stage | Decision |
| --- | ---: | ---: | --- | --- |
| `rate_up_short_1000` | 0.0 | 0.0 | `limited_core_grid_test` | FAIL |
| `rate_down_long_1000` | 0.0 | 0.0 | `limited_core_grid_test` | FAIL |
| `rate_up_high_level_short_1030` | 0.027777777777777776 | 0.08333333333333333 | `limited_core_grid_test` | FAIL |
| `bear_steepening_short_1130` | 0.0 | 0.0 | `limited_core_grid_test` | FAIL |
| `bull_flattening_long_1130` | 0.0 | 0.0 | `limited_core_grid_test` | FAIL |

Conclusion: no Treasury-rate shock variant reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.

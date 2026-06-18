# ES prior-session flip retest orderflow rescue attempt 1 - 2026-06-18

No paid data was downloaded. Rescue used only the local Sierra ES aggregate-orderflow cache.

Scope: one parameter-space/fixed-parameter rescue for each failed original variant. Entry module, stop module, target module, costs, sessions, data, fill model, and validation gates were unchanged.

| variant | original top net | rescue top net | rescue top PF | rescue top trades/year | rescue result |
|---|---:|---:|---:|---:|---|
| `afternoon_large10_aligned_two_sided_flip` | -4367.5 | -38.75 | 0.9977064220183486 | 90.98917839163146 | failed limited_core_grid_test |
| `late_morning_large10_absorbed_two_sided_flip` | -3755.625 | -1744.375 | 0.9245920242083648 | 115.62719064002087 | failed limited_core_grid_test |
| `midday_signed_aligned_two_sided_flip` | -2553.75 | -1857.5 | 0.8941444650235076 | 107.15143384202582 | failed limited_core_grid_test |
| `morning_signed_absorbed_two_sided_flip` | -2491.25 | -1682.5 | 0.568313021167415 | 50.99282686878083 | failed limited_core_grid_test |
| `morning_signed_aligned_two_sided_flip` | -4677.5 | -2893.75 | 0.7029004106776181 | 99.9253156396912 | failed limited_core_grid_test |

Decision: completed_failed. All five rescues failed limited_core_grid_test; no WFA or Monte Carlo was reached.

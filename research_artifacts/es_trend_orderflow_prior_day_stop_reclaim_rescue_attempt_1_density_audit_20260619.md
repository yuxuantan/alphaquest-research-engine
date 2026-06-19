# ES Trend-Orderflow Prior-Day Stop-Reclaim Rescue 1 Pre-PnL Density Audit

Date: 2026-06-19

Purpose: verify the exact `parameter_space_rescue_1` configs clear the 50 signals/year floor before any staged PnL is run.

Result: INVALIDATED BY STAGED RUNNER

Important correction: this standalone vectorized density audit overcounted relative to the actual
`trend_orderflow_pdh_pdl_sweep_reclaim` entry-module state machine used by the staged runner. Treat the
table below as a preliminary rejected approximation, not as accepted evidence. The authoritative staged
`limited_core_grid_test` summaries showed rescue1 max trades/year of only `49.787067` to `53.151059`,
median trades/year of `35.171188` to `38.734815`, and only `0` to `9` of `81` combinations meeting
50 trades/year depending on variant. All five rescue runs failed `limited_core_grid_test`.

Rules used:
- Same canonicalized limited-core random 10% contiguous window as the staged runner.
- Same full configured RTH range as each rescue config.
- Entry-module signal conditions only; stop/target and PnL were not evaluated.
- Every declared entry-parameter corner must produce at least 50 signals/year in both scopes.

Detail CSV: `research_artifacts/es_trend_orderflow_prior_day_stop_reclaim_rescue_attempt_1_density_audit_20260619.csv`
Summary CSV: `research_artifacts/es_trend_orderflow_prior_day_stop_reclaim_rescue_attempt_1_density_summary_20260619.csv`

| variant | scope | period | combos | min sig/yr | median sig/yr | max sig/yr | pass | weakest combo | strongest combo |
|---|---|---:|---:|---:|---:|---:|---|---|---|
| `afternoon_large20_two_sided_trend_absorption_1500` | full_configured_data | 2011-01-03 to 2026-06-09 | 9 | 80.165765 | 89.627528 | 97.857967 | True | sweep=2, imbalance=0.08 | sweep=0, imbalance=0.0 |
| `afternoon_large20_two_sided_trend_absorption_1500` | limited_core_grid_test | 2011-02-22 to 2012-09-06 | 9 | 61.741548 | 75.389680 | 90.337633 | True | sweep=2, imbalance=0.08 | sweep=0, imbalance=0.0 |
| `late_morning_signed_two_sided_trend_absorption_1230` | full_configured_data | 2011-01-03 to 2026-06-09 | 9 | 76.406982 | 88.849849 | 98.700452 | True | sweep=2, imbalance=0.04 | sweep=0, imbalance=0.0 |
| `late_morning_signed_two_sided_trend_absorption_1230` | limited_core_grid_test | 2011-02-22 to 2012-09-06 | 9 | 76.039591 | 86.438167 | 94.887011 | True | sweep=2, imbalance=0.04 | sweep=0, imbalance=0.0 |
| `midday_large10_two_sided_trend_absorption_1400` | full_configured_data | 2011-01-03 to 2026-06-09 | 9 | 76.536595 | 87.618524 | 97.209901 | True | sweep=2, imbalance=0.06 | sweep=0, imbalance=0.0 |
| `midday_large10_two_sided_trend_absorption_1400` | limited_core_grid_test | 2011-02-22 to 2012-09-06 | 9 | 62.391459 | 77.339413 | 91.637456 | True | sweep=2, imbalance=0.06 | sweep=0, imbalance=0.0 |
| `morning_pdh_signed_trend_absorption_short_1130` | full_configured_data | 2011-01-03 to 2026-06-09 | 9 | 76.406982 | 88.849849 | 98.700452 | True | sweep=2, imbalance=0.04 | sweep=0, imbalance=0.0 |
| `morning_pdh_signed_trend_absorption_short_1130` | limited_core_grid_test | 2011-02-22 to 2012-09-06 | 9 | 76.039591 | 86.438167 | 94.887011 | True | sweep=2, imbalance=0.04 | sweep=0, imbalance=0.0 |
| `morning_pdl_signed_trend_absorption_long_1130` | full_configured_data | 2011-01-03 to 2026-06-09 | 9 | 76.406982 | 88.849849 | 98.700452 | True | sweep=2, imbalance=0.04 | sweep=0, imbalance=0.0 |
| `morning_pdl_signed_trend_absorption_long_1130` | limited_core_grid_test | 2011-02-22 to 2012-09-06 | 9 | 76.039591 | 86.438167 | 94.887011 | True | sweep=2, imbalance=0.04 | sweep=0, imbalance=0.0 |

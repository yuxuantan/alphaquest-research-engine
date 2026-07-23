# nq_import_export_price_pressure Signal Density Audit

Date: 2026-06-23

Verdict: PASS.

This post-reform pre-PnL audit computed the same completed-bar entry conditions as `import_export_price_pressure`: lagged monthly import/export price-index ranks mapped by conservative availability date, completed NQ price movement from the RTH open through the signal bar, and cumulative configured NQ orderflow through that completed bar. No stops, targets, fills, PnL, stage outcomes, or post-entry prices were evaluated.

Initial rejected audit: `research_artifacts/nq_import_export_price_pressure_initial_density_rejected_20260623.md`
Sessions: 3813
Years (252-session): 15.130952
Latest-252 start: 2025-06-09
Min signals/year: 50.294256
Max signals/year: 58.092840
Min latest-252 signals/year: 55.000000

| variant_id | min_signals_per_year | max_signals_per_year | grid_rows |
| --- | ---: | ---: | ---: |
| core_pressure_large20_short_1200 | 50.294256 | 51.682140 | 2 |
| core_pressure_signed_short_1100 | 57.828482 | 58.092840 | 2 |
| import_disinflation_large20_long_1200 | 50.624705 | 51.483871 | 2 |
| import_disinflation_large20_long_1430 | 50.360346 | 51.219512 | 2 |
| import_disinflation_signed_long_1030 | 53.202203 | 54.061369 | 2 |

Detailed CSV: `research_artifacts/nq_import_export_price_pressure_density_audit_20260623.csv`
All declared entry-grid rows clear both the 50 signals/year full-history screen and the latest-252-session sanity screen.

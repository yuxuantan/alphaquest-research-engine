# nq_import_export_price_pressure Signal Density Audit

Date: 2026-06-23

Verdict: FAIL.

This pre-PnL audit computed the same completed-bar entry conditions as `import_export_price_pressure`: lagged monthly import/export price-index ranks mapped by conservative availability date, completed NQ price movement from the RTH open through the signal bar, and cumulative configured NQ orderflow through that completed bar. No stops, targets, fills, PnL, stage outcomes, or post-entry prices were evaluated.

Sessions: 3813
Years (252-session): 15.130952
Latest-252 start: 2025-06-09
Min signals/year: 41.306058
Max signals/year: 58.092840
Min latest-252 signals/year: 46.000000

| variant_id | min_signals_per_year | max_signals_per_year | grid_rows |
| --- | ---: | ---: | ---: |
| core_pressure_large20_short_1200 | 44.742722 | 46.527144 | 3 |
| core_pressure_signed_short_1100 | 56.771046 | 58.092840 | 3 |
| import_disinflation_large20_long_1200 | 41.900865 | 43.288749 | 3 |
| import_disinflation_large20_long_1430 | 41.306058 | 42.363493 | 3 |
| import_disinflation_signed_long_1030 | 48.575924 | 50.162077 | 3 |

Detailed CSV: `research_artifacts/nq_import_export_price_pressure_density_audit_20260623.csv`
At least one declared entry-grid row fails the 50 signals/year full-history density screen.

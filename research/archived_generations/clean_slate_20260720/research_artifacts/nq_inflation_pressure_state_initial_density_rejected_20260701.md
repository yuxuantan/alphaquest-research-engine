# NQ Inflation Pressure State Density Audit

Pre-PnL signal-density screen only. No trade PnL, stops, targets, or equity curves were inspected.

- Detail CSV: `research_artifacts/nq_inflation_pressure_state_density_audit_20260701.csv`
- Summary CSV: `research_artifacts/nq_inflation_pressure_state_density_summary_20260701.csv`
- Feature CSV: `data/external/nq_inflation_pressure_state_features_20110103_20260612.csv`
- Density pass rows: 33/45
- Passing variants: 2/5
- Minimum required signals per year: 50.0

| Variant | Rows Passed | Min Signals/Yr | Max Signals/Yr | Verdict |
|---|---:|---:|---:|---|
| core_cpi_accel_short_1200 | 9/9 | 64.219780 | 162.556319 | PASS |
| core_pce_disinflation_long_1030 | 3/9 | 2.608929 | 98.453627 | FAIL |
| core_pce_high_short_1000 | 6/9 | 0.000000 | 248.851648 | FAIL |
| cpi_high_short_1130 | 9/9 | 109.659204 | 209.717720 | PASS |
| pce_disinflation_long_1330 | 6/9 | 19.065247 | 106.096429 | FAIL |

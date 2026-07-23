# NQ Industrial Production State Density Audit

Pre-PnL signal-density screen only. No trade PnL, stops, targets, or equity curves were inspected.

- Detail CSV: `research_artifacts/nq_industrial_production_state_density_audit_20260701.csv`
- Summary CSV: `research_artifacts/nq_industrial_production_state_density_summary_20260701.csv`
- Feature CSV: `data/external/nq_industrial_production_state_features_20110103_20260612.csv`
- Density pass rows: 35/45
- Passing variants: 2/5
- Minimum required signals per year: 50.0

| Variant | Rows Passed | Min Signals/Yr | Max Signals/Yr | Verdict |
|---|---:|---:|---:|---|
| capacity_high_short_1330 | 3/9 | 0.000000 | 132.782852 | FAIL |
| indpro_3m_strength_long_1200 | 9/9 | 78.762901 | 155.666071 | PASS |
| ipman_3m_strength_short_1030 | 9/9 | 71.637968 | 169.580357 | PASS |
| ipman_3m_weakness_long_1000 | 8/9 | 35.655357 | 138.158938 | FAIL |
| ipman_6m_weakness_long_1130 | 6/9 | 16.523214 | 141.915721 | FAIL |

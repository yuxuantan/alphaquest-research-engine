# NQ Housing Construction State Density Audit

Pre-PnL signal-density screen only. No trade PnL, stops, targets, or equity curves were inspected.

- Detail CSV: `research_artifacts/nq_housing_construction_state_density_audit_20260701.csv`
- Summary CSV: `research_artifacts/nq_housing_construction_state_density_summary_20260701.csv`
- Feature CSV: `data/external/nq_housing_construction_state_features_20110103_20260612.csv`
- Density pass rows: 37/45
- Passing variants: 2/5
- Minimum required signals per year: 50.0

| Variant | Rows Passed | Min Signals/Yr | Max Signals/Yr | Verdict |
|---|---:|---:|---:|---|
| permit_starts_ratio_high_long_1330 | 9/9 | 79.271291 | 132.847624 | PASS |
| permits_3m_strength_long_1000 | 9/9 | 81.278159 | 189.582143 | PASS |
| permits_3m_weakness_short_1030 | 6/9 | 33.046429 | 129.442995 | FAIL |
| single_family_permits_strength_long_1200 | 7/9 | 19.065247 | 188.712500 | FAIL |
| starts_3m_weakness_short_1130 | 6/9 | 20.001786 | 92.688908 | FAIL |

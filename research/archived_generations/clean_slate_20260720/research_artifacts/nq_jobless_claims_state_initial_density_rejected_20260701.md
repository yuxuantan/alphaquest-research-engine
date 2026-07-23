# NQ Jobless Claims State Density Audit

Pre-PnL signal-density screen only. No trade PnL, stops, targets, or equity curves were inspected.

- Detail CSV: `research_artifacts/nq_jobless_claims_state_density_audit_20260701.csv`
- Summary CSV: `research_artifacts/nq_jobless_claims_state_density_summary_20260701.csv`
- Feature CSV: `data/external/nq_jobless_claims_state_features_20110103_20260612.csv`
- Density pass rows: 35/45
- Passing variants: 3/5
- Minimum required signals per year: 50.0

| Variant | Rows Passed | Min Signals/Yr | Max Signals/Yr | Verdict |
|---|---:|---:|---:|---|
| claims_high_short_1030 | 3/9 | 0.000000 | 105.360577 | FAIL |
| claims_improving_long_1330 | 9/9 | 85.952607 | 135.463599 | PASS |
| claims_low_long_1000 | 9/9 | 92.315934 | 239.151786 | PASS |
| claims_rising_short_1130 | 9/9 | 56.192308 | 115.942100 | PASS |
| continued_claims_high_short_1200 | 5/9 | 0.000000 | 156.535714 | FAIL |

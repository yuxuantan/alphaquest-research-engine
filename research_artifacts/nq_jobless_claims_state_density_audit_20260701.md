# NQ Jobless Claims State Density Audit

Pre-PnL signal-density screen only. No trade PnL, stops, targets, or equity curves were inspected.

- Detail CSV: `research_artifacts/nq_jobless_claims_state_density_audit_20260701.csv`
- Summary CSV: `research_artifacts/nq_jobless_claims_state_density_summary_20260701.csv`
- Feature CSV: `data/external/nq_jobless_claims_state_features_20110103_20260612.csv`
- Density pass rows: 45/45
- Passing variants: 5/5
- Minimum required signals per year: 50.0

| Variant | Rows Passed | Min Signals/Yr | Max Signals/Yr | Verdict |
|---|---:|---:|---:|---|
| claims_improving_long_1130 | 9/9 | 85.952607 | 135.463599 | PASS |
| claims_low_long_1000 | 9/9 | 92.315934 | 239.151786 | PASS |
| claims_rising_short_1030 | 9/9 | 56.192308 | 115.942100 | PASS |
| continued_claims_improving_long_1330 | 9/9 | 66.962500 | 187.642170 | PASS |
| continued_claims_rising_short_1200 | 9/9 | 52.178571 | 131.316071 | PASS |

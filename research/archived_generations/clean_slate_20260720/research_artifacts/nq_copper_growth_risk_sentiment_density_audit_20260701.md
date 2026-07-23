# NQ Copper Growth/Risk Sentiment Density Audit

Pre-PnL signal-density screen only. No trade PnL, stops, targets, or equity curves were inspected.

- Detail CSV: `research_artifacts/nq_copper_growth_risk_sentiment_density_audit_20260701.csv`
- Summary CSV: `research_artifacts/nq_copper_growth_risk_sentiment_density_summary_20260701.csv`
- Feature CSV: `data/external/nq_copper_growth_risk_sentiment_features_20110103_20260612.csv`
- Density pass rows: 45/45
- Passing variants: 5/5
- Minimum required signals per year: 50.0

| Variant | Rows Passed | Min Signals/Yr | Max Signals/Yr | Verdict |
|---|---:|---:|---:|---|
| copper_1d_strength_long_1000 | 9/9 | 76.528571 | 111.381181 | PASS |
| copper_1d_weakness_short_1000 | 9/9 | 87.248049 | 120.010714 | PASS |
| copper_3d_strength_long_1030 | 9/9 | 77.398214 | 111.381181 | PASS |
| copper_gold_ratio_strength_long_1130 | 9/9 | 84.355357 | 118.405220 | PASS |
| copper_gold_ratio_weakness_short_1330 | 9/9 | 79.271291 | 115.662500 | PASS |

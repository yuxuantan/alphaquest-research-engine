# NQ BTC Crypto Risk Sentiment Density Audit

Pre-PnL signal-density screen only. No trade PnL, stops, targets, or equity curves were inspected.

- Detail CSV: `research_artifacts/nq_btc_crypto_risk_sentiment_density_audit_20260701.csv`
- Summary CSV: `research_artifacts/nq_btc_crypto_risk_sentiment_density_summary_20260701.csv`
- Feature CSV: `data/external/nq_btc_crypto_risk_sentiment_features_20150115_20260612.csv`
- Density pass rows: 45/45
- Passing variants: 5/5
- Minimum required signals per year: 50.0

| Variant | Rows Passed | Min Signals/Yr | Max Signals/Yr | Verdict |
|---|---:|---:|---:|---|
| btc_1d_strength_long_1000 | 9/9 | 83.011364 | 112.384615 | PASS |
| btc_1d_weakness_short_1000 | 9/9 | 73.399522 | 119.408654 | PASS |
| btc_3d_strength_long_1030 | 9/9 | 83.885167 | 114.391484 | PASS |
| btc_3d_weakness_short_1130 | 9/9 | 69.904306 | 111.381181 | PASS |
| btc_volatility_riskoff_short_1330 | 9/9 | 66.409091 | 128.439560 | PASS |

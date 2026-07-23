# ES Dollar Risk-Appetite Intraday Density Audit - 2026-06-17

Decision: eligible for staged testing.

Scope:

- Campaign: `es_dollar_risk_appetite_intraday`
- ES bars: `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
- Dollar source: free FRED/Federal Reserve `DTWEXBGS`
- Feature cache: `data/external/es_dollar_risk_appetite_features_20110103_20260609.csv`
- Availability rule: latest dollar-index observation on or before ES session date minus one business day.

Feature build:

- Rows: 3817 ES RTH sessions.
- Valid 252-rank rows: 3760.
- Date range: `2011-01-03` through `2026-06-09`.
- No paid data was downloaded.

Pre-test density check:

| Condition | Eligible sessions | Approx. sessions/year |
| --- | ---: | ---: |
| one-day dollar return rank >= 0.55 | 1719 | 111.40 |
| one-day dollar return rank >= 0.65 | 1338 | 86.71 |
| one-day dollar return rank <= 0.45 | 1660 | 107.58 |
| one-day dollar return rank <= 0.35 | 1263 | 81.85 |
| one-day dollar return rank >= 0.65 and dollar level rank >= 0.65 | 826 | 53.53 |
| one-day dollar return rank >= 0.55 and dollar level rank >= 0.55 | 1143 | 74.07 |
| five-day dollar return rank >= 0.65 | 1344 | 87.10 |
| five-day dollar return rank <= 0.35 | 1278 | 82.82 |

Conclusion:

All five predeclared variants are dense enough to plausibly satisfy the
`>=50` trades/year methodology rule before costs and exits. The campaign may
proceed to staged testing without relaxing the density standard.

Verification:

- `python3 -m pytest tests/test_dollar_risk_appetite.py` -> PASS, 2 tests.
- `python3 -m research.preflight --skip-tests --config <five dollar configs>` -> PASS, 5 configs.

# ES Cboe Implied Correlation Density Audit - 2026-06-17

Decision: PASS density precheck for campaign testing.

Data source: free official Cboe COR1M/COR3M CSV endpoints, cached at `data/external/cboe_cor1m_history.csv` and `data/external/cboe_cor3m_history.csv`. No paid data was downloaded.

Feature file: `data/external/es_cboe_implied_correlation_features_20110103_20260609.csv`.

- Rows: 3817 ES RTH sessions.
- Valid rank rows: 3759.
- Date range: 2011-01-03 through 2026-06-09.
- Lookahead control: `merge_asof(..., allow_exact_matches=False)`, so every ES session uses only the latest prior Cboe implied-correlation close.
- Planned thresholds produce about 70 to 133 eligible sessions per year before fills and benchmark filters.

Conclusion: the edge is dense enough to try under the 50 trades/year gate, but it must fail closed if results are narrow or crisis-concentrated.

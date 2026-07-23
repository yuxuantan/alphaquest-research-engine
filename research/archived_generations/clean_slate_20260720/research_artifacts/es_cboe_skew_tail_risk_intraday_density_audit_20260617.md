# ES Cboe SKEW Tail Risk Density Audit - 2026-06-17

Decision: PASS density precheck for campaign testing.

Data source: free official Cboe SKEW CSV endpoint, cached at `data/external/cboe_skew_history.csv`. No paid data was downloaded.

Feature file: `data/external/es_cboe_skew_tail_risk_features_20110103_20260609.csv`.

- Rows: 3817 ES RTH sessions.
- Valid rank rows: 3758.
- Date range: 2011-01-03 through 2026-06-09.
- Lookahead control: `merge_asof(..., allow_exact_matches=False)`, so every ES session uses only the latest prior Cboe SKEW close.
- Planned thresholds produce about 83 to 119 eligible sessions per year before fills and benchmark filters.

Conclusion: the edge is dense enough to try under the 50 trades/year gate, but it remains close to other option-tail-risk families and must fail closed if results are narrow or crisis-concentrated.

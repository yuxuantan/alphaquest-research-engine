# ES Cboe VIX Term Structure Density Audit - 2026-06-17

Decision: PASS density precheck for campaign testing.

Data source: free official Cboe VIX9D, VIX, VIX3M, and VIX6M CSV endpoints, cached under `data/external/`. No paid data was downloaded.

Feature file: `data/external/es_cboe_vix_term_structure_features_20110103_20260609.csv`.

- Rows: 3817 ES RTH sessions.
- Valid rank rows: 3757.
- Date range: 2011-01-03 through 2026-06-09.
- Lookahead control: `merge_asof(..., allow_exact_matches=False)`, so every ES session uses only the latest prior Cboe volatility-index close.
- Planned thresholds produce about 83 to 116 eligible sessions per year before fills and benchmark filters.

Conclusion: the edge is dense enough to try under the 50 trades/year gate, but it must fail closed if results are narrow or crisis-concentrated.

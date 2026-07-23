# Pre-Campaign Density Rejections - 2026-06-20

These edges were screened before campaign authoring and rejected without PnL testing because they did not satisfy the user-required trade-frequency feasibility rule. No paid data was downloaded.

## Corporate Buyback Blackout / Resumption Calendar Proxy

- Proposed mechanism: reduced corporate repurchase demand during quarterly blackout windows and renewed demand after earnings-season resumption, traded only with completed ES price and aggregate orderflow confirmation.
- Data used for screening: local Sierra ES RTH 1-minute orderflow cache and deterministic quarter-end calendar windows.
- Screen artifact: `research_artifacts/es_buyback_blackout_orderflow_density_screen_20260620.csv`.
- Result: rejected before campaign authoring. No screened blackout or resumption shape reached 50 trades/year in all full, limited-core, WFA90, and latest-year reference windows. The best blackout short shapes were roughly 20-43 trades/year in the limiting windows after confirmation.

## Real-Yield / Breakeven Decomposition Orderflow Confirmation

- Proposed mechanism: real-rate and inflation-expectation decomposition of Treasury moves, distinct from nominal-rate direction, traded only when completed ES price and aggregate orderflow confirm.
- Data used for screening: free public FRED `DFII10`, `T10YIE`, and `DGS10` CSVs plus local Sierra ES RTH 1-minute orderflow.
- Feature artifact: `data/external/es_real_yield_breakeven_features_20110103_20260609.csv`.
- Screen artifact: `research_artifacts/es_real_yield_breakeven_orderflow_density_screen_20260620.csv`.
- Result: rejected before campaign authoring. No screened real-yield or breakeven shape reached 50 trades/year in all required reference windows; the best dense-looking cases were about 35-41 trades/year in limiting windows.

Decision: do not author campaigns for these edges unless the user explicitly changes the trade-count feasibility rule or provides a different, denser data/mechanics formulation.

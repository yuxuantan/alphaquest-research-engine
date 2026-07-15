# Methodology Audit: es_mes_trend_aoi_pullback

Verdict: FAIL

Pre-test controls:
- Five variants were declared before staged PnL testing in `campaigns/es_mes_trend_aoi_pullback/campaign.yaml`.
- Eight-variant expansion was not used because three narrower standalone AOI mechanics failed the pre-PnL density screen.
- The pre-PnL density audit was written to `research_artifacts/es_mes_trend_aoi_pullback_density_audit_20260622.md`.
- Grid dimensions were fixed at two entry tunables, one stop tunable, and one target tunable, for 81 combinations per variant.
- Data source was the derived local 1-minute ES/MES participation-crowding plus true VAP/overnight/footprint cache.
- Signals use a completed prior ES trend window that ends before the MES pullback window, completed AOI reclaim/reject bars, and next-bar execution through `mes_trend_aoi_pullback`.

Result:
- All five variants failed `limited_core_grid_test`.
- No variant reached monkey testing, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.
- No rescue was used.

Failure interpretation:
The trend-aligned MES-crowding AOI pullback edge is rejected as tested. The best top configuration was `overnight_trade15_trend_pullback_1500` with 20/81 profitable iterations, top net 1045.0, top PF 2.1483516483516483, and failure reason `min_trades_per_year;preferred_min_total_trades;max_best_day_concentration`. This does not clear the first objective rejection gate.

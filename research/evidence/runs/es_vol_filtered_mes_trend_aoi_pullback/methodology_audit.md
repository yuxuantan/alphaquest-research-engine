# Methodology Audit: es_vol_filtered_mes_trend_aoi_pullback

Verdict: FAIL

Pre-test controls:
- Eight variants were declared before staged PnL testing in `campaigns/es_vol_filtered_mes_trend_aoi_pullback/campaign.yaml`.
- Eight-variant expansion was used under the updated policy because value-area, prior-extreme, and LVN variants are distinct AOI mechanics and cleared pre-PnL density checks before any backtest result was inspected.
- The pre-PnL density audit was written to `research_artifacts/es_vol_filtered_mes_trend_aoi_pullback_density_audit_20260622.md`.
- Grid dimensions were fixed at two entry tunables, one stop tunable, and one target tunable, for 81 combinations per variant.
- The lagged volatility gate column and threshold were fixed per variant and were not grid-tuned.
- Data source was the derived local 1-minute ES/MES participation-crowding plus true VAP/overnight/footprint cache, with prior RTH levels built by the feature pipeline.
- Signals use a completed prior ES trend window that ends before the MES pullback window, completed AOI reclaim/reject bars, prior-session volatility features, and next-bar execution through `vol_filtered_mes_trend_aoi_pullback`.

Result:
- All eight variants failed `limited_core_grid_test`.
- No variant reached monkey testing, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.
- No rescue was used.

Failure interpretation:
The edge is rejected as tested. The highest profitable-iteration variant was `lvn_trade15_vol_downshift_1500` with 32/81 profitable iterations, top net 485.0, top PF 2.1686746987951806, and failure reason `min_trades_per_year;preferred_min_total_trades;max_best_day_concentration`. The best top-net variant was `overnight_trade15_downside20_1500` with top net 1045.0, but it also failed the first objective rejection gate. Positive pockets were too sparse or concentrated to promote.

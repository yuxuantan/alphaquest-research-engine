# ES Vol-Filtered MES Trend AOI Pullback Density Audit

- Generated: 2026-06-22
- Source cache: `data/cache/orderflow/es_mes_crowding_vap_aoi_1m_20190506_20250529_rth_ny.parquet`
- Lagged volatility features: `data/external/es_lagged_volatility_features_20110103_20260609.csv`
- Decision: approve eight variants for testing before PnL because each variant expresses a distinct AOI or profile mechanic with a predeclared prior-session volatility gate.
- Strict corner: `min_share_rank=0.55`, `min_abs_return_ticks=4`, `min_trend_return_ticks=4`, `min_probe_ticks=1`; delta variants use `min_delta_imbalance=0.02`; the profile absorption variant requires completed footprint absorption.
- Caveat: MES participation is a smaller-contract crowding proxy, not account-classified retail data; volatility gates are prior-session features only.
- Pipeline rows: 585780; data span: 2019-05-06 through 2025-05-29.

| variant_id | signals | sessions | sessions/year | long | short | vol gate | window |
|---|---:|---:|---:|---:|---:|---|---|
| all_aoi_notional30_absret5_1500 | 657 | 657 | 108.3 | 330 | 327 | absret5_rank_252 <= 0.95 | 10:00:00-15:00:00 |
| market_trade15_absret5_1500 | 544 | 544 | 89.7 | 282 | 262 | absret5_rank_252 <= 0.95 | 10:00:00-15:00:00 |
| opening_trade15_range10_1200 | 226 | 226 | 37.3 | 123 | 103 | range10_rank_252 <= 0.95 | 10:00:00-12:00:00 |
| profile_trade15_absorption_absret5_1500 | 218 | 218 | 35.9 | 117 | 101 | absret5_rank_252 <= 0.95 | 10:00:00-15:00:00 |
| overnight_trade15_downside20_1500 | 216 | 216 | 35.6 | 119 | 97 | downside20_rank_252 <= 0.95 | 10:00:00-15:00:00 |
| value_area_trade15_downside20_1500 | 207 | 207 | 34.1 | 96 | 111 | downside20_rank_252 <= 0.95 | 10:00:00-15:00:00 |
| prior_extreme_trade15_range10_1500 | 181 | 181 | 29.8 | 94 | 87 | range10_rank_252 <= 0.95 | 10:00:00-15:00:00 |
| lvn_trade15_vol_downshift_1500 | 178 | 178 | 29.4 | 88 | 90 | vol5_over_vol20 <= 1.25 | 10:00:00-15:00:00 |

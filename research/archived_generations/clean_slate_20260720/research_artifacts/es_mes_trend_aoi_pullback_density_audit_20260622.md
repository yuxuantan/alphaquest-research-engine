# ES MES Trend AOI Pullback Density Audit

- Generated: 2026-06-22
- Source cache: `data/cache/orderflow/es_mes_crowding_vap_aoi_1m_20190506_20250529_rth_ny.parquet`
- Decision: FAIL density for sparse variants. Minimum selected strict-corner density is 33.5 sessions/year.
- Strict corner: `min_share_rank=0.55`, `min_abs_return_ticks=4`, `min_trend_return_ticks=4`, `min_probe_ticks=1`; delta variants use `min_delta_imbalance=0.02` and the profile absorption variant requires completed footprint absorption.
- Caveat: MES participation is a smaller-contract crowding proxy, not account-classified retail data; trend and AOI fields are completed-bar only.

| variant_id | raw signals | sessions | sessions/year | window |
|---|---:|---:|---:|---|
| all_aoi_notional30_trend_pullback_1500 | 2135 | 695 | 114.6 | 10:00:00-15:00:00 |
| market_trade15_trend_pullback_1500 | 1395 | 621 | 102.4 | 10:00:00-15:00:00 |
| opening_trade15_trend_pullback_1200 | 378 | 262 | 43.2 | 10:00:00-12:00:00 |
| overnight_trade15_trend_pullback_1500 | 427 | 260 | 42.9 | 10:00:00-15:00:00 |
| profile_trade15_absorption_pullback_1500 | 382 | 260 | 42.9 | 10:00:00-15:00:00 |
| value_area_trade15_trend_pullback_1500 | 465 | 245 | 40.4 | 10:00:00-15:00:00 |
| prior_extreme_trade15_trend_pullback_1500 | 355 | 203 | 33.5 | 10:00:00-15:00:00 |
| lvn_trade15_trend_pullback_1500 | 355 | 203 | 33.5 | 10:00:00-15:00:00 |

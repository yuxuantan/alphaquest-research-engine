# ES MES Crowding AOI Trap Reversion Density Audit

- Generated: 2026-06-22
- Source cache: `data/cache/orderflow/es_mes_crowding_vap_aoi_1m_20190506_20250529_rth_ny.parquet`
- Decision: PASS density for staged testing. All selected variants clear at least 50 signal sessions/year at the strict pre-PnL corner.
- Strict corner: `min_share_rank=0.65`, `min_abs_return_ticks=4`, `min_probe_ticks=1`; delta variants use `min_delta_imbalance=0.02`, absorption variant requires completed footprint absorption.
- Caveat: MES participation is a smaller-contract crowding proxy, not account-classified retail data; footprint/VAP fields are completed-bar research features.

| variant_id | raw signals | sessions | sessions/year | window |
|---|---:|---:|---:|---|
| all_aoi_notional30_delta_1500 | 5836 | 904 | 149.1 | 10:00:00-15:00:00 |
| market_aoi_trade15_delta_1500 | 3988 | 883 | 145.6 | 10:00:00-15:00:00 |
| opening_range_trade15_delta_1200 | 1379 | 603 | 99.4 | 10:00:00-12:00:00 |
| overnight_trade15_delta_1500 | 1206 | 500 | 82.4 | 10:00:00-15:00:00 |
| profile_aoi_trade15_absorption_1500 | 887 | 431 | 71.1 | 10:00:00-15:00:00 |
| value_area_trade15_delta_1500 | 1070 | 394 | 65.0 | 10:00:00-15:00:00 |
| prior_extreme_trade15_delta_1500 | 894 | 371 | 61.2 | 10:00:00-15:00:00 |
| lvn_trade15_delta_1500 | 893 | 370 | 61.0 | 10:00:00-15:00:00 |

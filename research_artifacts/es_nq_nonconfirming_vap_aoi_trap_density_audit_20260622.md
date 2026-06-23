# ES NQ Nonconfirming VAP AOI Trap Density Audit

- Generated: 2026-06-22
- Source cache: `data/cache/orderflow/es_sierra_footprint_vap_overnight_aoi_nq_leadlag_1m_20110103_20260529_rth_ny.parquet`
- Source lineage: timestamp join of true VAP/overnight/footprint ES cache with completed ES/NQ rolling lead-lag cache.
- Decision: PASS density for staged testing. All eight selected variants clear the limited-core 50 sessions/year screen at the strict positive-delta corner; all but one also clear 50 sessions/year on the full sample.
- Caveat: Dense variants use VAP context (`beyond_poc` or `near_side_value`) rather than exact VAP-node price confluence. Exact node confluence plus NQ non-confirmation was rejected before PnL as too sparse.
- Strict corner used here: `min_nq_es_return_gap_bps=0.5`, `min_adverse_delta_imbalance=0.005`, and fixed `min_probe_ticks` as listed by variant.

| variant_id | setup_mode | profile_context | nq_window | probe_ticks | raw | sessions/year | limited/year |
|---|---|---:|---:|---:|---:|---:|---:|
| all_market_beyond_poc_nq30_1500 | all_market_profile_two_sided_trap | beyond_poc | 30 | 1 | 3169 | 117.205 | 113.734 |
| market_beyond_poc_nq30_1500 | market_profile_two_sided_trap | beyond_poc | 30 | 1 | 2222 | 91.816 | 81.239 |
| market_near_value_nq30_1500 | market_profile_two_sided_trap | near_side_value | 30 | 1 | 2136 | 88.764 | 80.589 |
| market_deep_probe_beyond_poc_nq30_1500 | market_profile_two_sided_trap | beyond_poc | 30 | 2 | 1446 | 68.44 | 50.043 |
| market_beyond_poc_nq15_1500 | market_profile_two_sided_trap | beyond_poc | 15 | 1 | 2098 | 89.413 | 79.939 |
| market_beyond_poc_nq60_1500 | market_profile_two_sided_trap | beyond_poc | 60 | 1 | 1771 | 75.647 | 65.641 |
| opening_beyond_poc_nq30_1500 | opening_profile_two_sided_trap | beyond_poc | 30 | 1 | 1288 | 58.245 | 57.192 |
| overnight_beyond_poc_nq30_1530 | overnight_profile_two_sided_trap | beyond_poc | 30 | 1 | 1173 | 52.271 | 55.892 |

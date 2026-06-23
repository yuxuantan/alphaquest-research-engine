# ES Low-Toxicity AOI False-Breakout Density Audit

- Generated: 2026-06-23
- Source cache: `data/cache/orderflow/es_sierra_footprint_vap_overnight_aoi_1m_20110103_20260529_rth_ny.parquet`
- Decision rule: approve only variants with enough strict-corner one-signal-per-day density before any PnL testing.
- Strict corner: `max_abs_delta_imbalance=0.12`, `min_probe_ticks=1`, `confirmation_ticks=0`, reversal body required; largequiet variants require `large20_volume / volume <= 0.10`.
- Caveat: signed-volume and large20 fields are completed-bar proxies, not full MBO or vendor-equivalent >200-lot print sequencing.
- Pipeline rows: 1485900; data span: 2011-01-03 through 2026-05-29.

| variant_id | signals | sessions | sessions/year | long | short | large max | top AOIs |
|---|---:|---:|---:|---:|---:|---:|---|
| all_aoi_signedquiet_1500 | 3629 | 3629 | 235.6 | 1689 | 1940 | none | opening_range_high:887;opening_range_low:733;overnight_high:326;prior_rth_high:319;overnight_low:308 |
| market_aoi_signedquiet_1500 | 3565 | 3565 | 231.5 | 1639 | 1926 | none | opening_range_high:1120;opening_range_low:925;overnight_high:408;overnight_low:408;prior_rth_high:398 |
| opening_aoi_signedquiet_1200 | 2745 | 2745 | 178.2 | 1309 | 1436 | none | opening_range_high:1436;opening_range_low:1309 |
| market_aoi_largequiet_1500 | 2422 | 2422 | 157.3 | 1111 | 1311 | 0.1 | opening_range_high:746;opening_range_low:636;overnight_high:290;prior_rth_high:275;overnight_low:269 |
| overnight_signedquiet_1500 | 2367 | 2367 | 153.7 | 1164 | 1203 | none | overnight_high:1203;overnight_low:1164 |
| value_area_signedquiet_1500 | 1903 | 1903 | 123.6 | 937 | 966 | none | prior_value_area_high:966;prior_value_area_low:937 |
| poc_signedquiet_1500 | 1414 | 1414 | 91.8 | 748 | 666 | none | prior_poc_reclaim:748;prior_poc_reject:666 |
| lvn_largequiet_1500 | 1192 | 1192 | 77.4 | 545 | 647 | 0.1 | prior_lvn_near_high:647;prior_lvn_near_low:545 |

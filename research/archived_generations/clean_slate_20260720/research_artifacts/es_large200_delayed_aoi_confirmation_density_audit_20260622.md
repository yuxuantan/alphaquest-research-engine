# ES Large200 Delayed AOI Confirmation Density Audit

- Generated: 2026-06-22
- Source cache: `data/cache/orderflow/es_sierra_footprint_vap_overnight_large200_1m_20120103_20260529_rth_ny.parquet`
- Decision: PASS density for staged testing. All selected variants clear the limited-core density screen; several are below 50 sessions/year on the full sample, but all have more than 80 limited-core sessions/year at the strict pre-PnL corner and are included because they express distinct AOI mechanics.
- Strict corner: `min_large200_record_volume=200`, `min_confirm_delta_imbalance=0.02`, `min_probe_ticks=1`, one-bar delayed confirmation.
- Caveat: `large200_record_*` fields are a strict Sierra SCID record proxy, not vendor-equivalent print truth.

| variant_id | setup_mode | raw | sessions/year | limited/year |
|---|---|---:|---:|---:|
| all_aoi_delayed_trap_1500 | all_aoi_delayed_trap | 1938 | 77.3 | 167.1 |
| market_aoi_delayed_trap_1500 | market_aoi_delayed_trap | 1450 | 63.5 | 145.8 |
| opening_aoi_delayed_trap_1200 | opening_aoi_delayed_trap | 597 | 31.9 | 86.0 |
| overnight_aoi_delayed_trap_1530 | overnight_aoi_delayed_trap | 845 | 40.8 | 99.1 |
| value_area_delayed_trap_1500 | value_area_delayed_trap | 770 | 36.2 | 83.9 |
| all_aoi_delayed_continuation_1500 | all_aoi_delayed_continuation | 2968 | 59.4 | 95.6 |
| market_aoi_delayed_continuation_1500 | market_aoi_delayed_continuation | 2686 | 54.0 | 89.4 |
| value_area_delayed_continuation_1500 | value_area_delayed_continuation | 9788 | 155.5 | 229.7 |

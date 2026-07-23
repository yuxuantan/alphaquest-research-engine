# ES True VAP Value-Area Orderflow Acceptance Density Audit

Pre-PnL density screen only. No profit, drawdown, or target/stop result was used.

Data: `data/cache/orderflow/es_sierra_footprint_vap_overnight_aoi_1m_20110103_20260529_rth_ny.parquet`

Rows: 1,485,900

Period: 2011-01-03 through 2026-05-29 RTH

Strict entry corner: `breakout_buffer_ticks=2`, `min_orderflow_imbalance=0.04`.

| Variant | Raw Eligible Bars | Sessions | Full Signals/Year | Limited-Core Sessions | Limited-Core Signals/Year |
|---|---:|---:|---:|---:|---:|
| morning_true_vah_signed_acceptance_long_1130 | 69,859 | 2,131 | 138.4 | 214 | 127.7 |
| morning_true_val_signed_acceptance_short_1130 | 50,305 | 1,714 | 111.3 | 195 | 116.4 |
| morning_inside_value_escape_signed_two_sided_1130 | 2,820 | 943 | 61.2 | 103 | 61.5 |
| late_morning_true_value_large10_two_sided_1230 | 180,030 | 3,562 | 231.3 | 383 | 228.6 |
| midday_true_value_large20_two_sided_1400 | 195,303 | 3,512 | 228.0 | 369 | 220.2 |
| afternoon_true_value_signed_two_sided_1500 | 175,970 | 3,490 | 226.6 | 369 | 220.2 |
| morning_gap_above_vah_hold_footprint_long_1030 | 23,590 | 1,452 | 94.3 | 149 | 88.9 |
| morning_gap_below_val_hold_footprint_short_1030 | 15,747 | 993 | 64.5 | 120 | 71.6 |

Decision: approve for staged testing. All eight variants clear the 50 signals/year density floor before PnL is inspected.

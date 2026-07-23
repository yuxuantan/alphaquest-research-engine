# ES Cboe VXN/VIX Dispersion Density Audit - 2026-06-17

Campaign: `es_cboe_vxn_vix_dispersion_intraday`

Data sources:
- Local ES Sierra RTH 1-minute cache: `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
- Free official Cboe daily histories:
  - `https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv`
  - `https://cdn.cboe.com/api/global/us_indices/daily_prices/VXN_History.csv`

Feature file:
- Builder: `tools/build_es_cboe_vxn_vix_dispersion_features.py`
- Output: `data/external/es_cboe_vxn_vix_dispersion_features_20110103_20260609.csv`
- Rows: 3817
- Valid rank rows: 3817
- Date range: 2011-01-03 through 2026-06-09
- Lookahead control: ES session features use the latest completed Cboe VIX and VXN closes strictly before the ES session date.

Original threshold density before fills:

| Setup proxy | Threshold | Eligible sessions | Years touched | Approx sessions/year |
|---|---:|---:|---:|---:|
| VXN/VIX ratio upper tail | >= 0.55 | 1839 | 16 | 114.9 |
| VXN/VIX ratio upper tail | >= 0.60 | 1674 | 16 | 104.6 |
| VXN/VIX ratio upper tail | >= 0.65 | 1504 | 16 | 94.0 |
| VXN/VIX ratio lower tail | <= 0.45 | 1626 | 16 | 101.6 |
| VXN/VIX ratio lower tail | <= 0.40 | 1466 | 16 | 91.6 |
| VXN/VIX ratio lower tail | <= 0.35 | 1296 | 16 | 81.0 |
| VXN/VIX ratio change upper tail | >= 0.55 | 1733 | 16 | 108.3 |
| VXN/VIX ratio change upper tail | >= 0.60 | 1524 | 16 | 95.2 |
| VXN/VIX ratio change upper tail | >= 0.65 | 1358 | 16 | 84.9 |
| VXN/VIX ratio change lower tail | <= 0.45 | 1717 | 16 | 107.3 |
| VXN/VIX ratio change lower tail | <= 0.40 | 1513 | 16 | 94.6 |
| VXN/VIX ratio change lower tail | <= 0.35 | 1321 | 16 | 82.6 |
| VXN-minus-VIX spread upper tail | >= 0.55 | 1753 | 16 | 109.6 |
| VXN-minus-VIX spread upper tail | >= 0.60 | 1596 | 16 | 99.8 |
| VXN-minus-VIX spread upper tail | >= 0.65 | 1427 | 16 | 89.2 |

Rescue threshold density before fills:

| Setup proxy | Thresholds | Approx sessions/year range |
|---|---|---:|
| VXN/VIX ratio upper tail | >= 0.70, 0.75, 0.80 | 59.8 to 82.9 |
| VXN/VIX ratio change upper tail | >= 0.68, 0.72, 0.76 | 57.4 to 77.3 |
| VXN/VIX ratio lower tail | <= 0.32, 0.28, 0.24 | 59.4 to 74.1 |
| VXN/VIX ratio change lower tail | <= 0.32, 0.28, 0.24 | 57.8 to 75.4 |
| VXN-minus-VIX spread upper tail | >= 0.70, 0.75, 0.80 | 57.2 to 78.2 |

Conclusion: All original and rescue threshold grids were dense enough to plausibly clear the 50 trades/year gate before fills and stage-level filtering.

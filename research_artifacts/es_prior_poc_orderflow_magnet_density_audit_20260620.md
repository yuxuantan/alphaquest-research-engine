# ES Prior POC Orderflow Magnet Density Audit

Date: 2026-06-20

Purpose: pre-PnL density gate before authoring/staging a campaign. A variant should not be staged if the strict corner is unlikely to reach 50 trades/year.

Full subset: 2011-01-03 to 2026-06-09.
Limited-core shortlist subset from runner default random_fraction policy: 2011-02-22 to 2012-09-06, avoiding last 10% and 2020-02-01 through 2021-06-30.

Implementation note: this uses the same local Sierra 1m aggregate-orderflow Parquet and the same prior-session OHLCV profile approximation as the entry module. It is a density-only screen, not profitability evidence.

## Strict Corner Summary

| dataset | variant_id | signals | signals_per_year | passes_50_per_year | long_signals | short_signals |
| --- | --- | --- | --- | --- | --- | --- |
| full | morning_above_poc_signed_magnet_short | 1680 | 110.91 | True | 0 | 1680 |
| full | morning_below_poc_signed_magnet_long | 1281 | 84.57 | True | 1281 | 0 |
| full | late_morning_large10_two_sided_magnet | 2691 | 177.66 | True | 1162 | 1529 |
| full | midday_signed_two_sided_magnet | 2433 | 160.63 | True | 1029 | 1404 |
| full | afternoon_large20_two_sided_magnet | 2357 | 155.61 | True | 999 | 1358 |
| limited_core_window | morning_above_poc_signed_magnet_short | 165 | 111.18 | True | 0 | 165 |
| limited_core_window | morning_below_poc_signed_magnet_long | 151 | 101.74 | True | 151 | 0 |
| limited_core_window | late_morning_large10_two_sided_magnet | 290 | 195.4 | True | 139 | 151 |
| limited_core_window | midday_signed_two_sided_magnet | 275 | 185.29 | True | 127 | 148 |
| limited_core_window | afternoon_large20_two_sided_magnet | 272 | 183.27 | True | 123 | 149 |

## All Corners

| dataset | variant_id | corner | signals | signals_per_year | passes_50_per_year | long_signals | short_signals |
| --- | --- | --- | --- | --- | --- | --- | --- |
| full | morning_above_poc_signed_magnet_short | loose | 1897 | 125.24 | True | 0 | 1897 |
| full | morning_above_poc_signed_magnet_short | mid | 1809 | 119.43 | True | 0 | 1809 |
| full | morning_above_poc_signed_magnet_short | strict | 1680 | 110.91 | True | 0 | 1680 |
| full | morning_below_poc_signed_magnet_long | loose | 1436 | 94.81 | True | 1436 | 0 |
| full | morning_below_poc_signed_magnet_long | mid | 1374 | 90.71 | True | 1374 | 0 |
| full | morning_below_poc_signed_magnet_long | strict | 1281 | 84.57 | True | 1281 | 0 |
| full | late_morning_large10_two_sided_magnet | loose | 2915 | 192.45 | True | 1265 | 1650 |
| full | late_morning_large10_two_sided_magnet | mid | 2816 | 185.91 | True | 1229 | 1587 |
| full | late_morning_large10_two_sided_magnet | strict | 2691 | 177.66 | True | 1162 | 1529 |
| full | midday_signed_two_sided_magnet | loose | 2683 | 177.13 | True | 1150 | 1533 |
| full | midday_signed_two_sided_magnet | mid | 2562 | 169.14 | True | 1091 | 1471 |
| full | midday_signed_two_sided_magnet | strict | 2433 | 160.63 | True | 1029 | 1404 |
| full | afternoon_large20_two_sided_magnet | loose | 2558 | 168.88 | True | 1087 | 1471 |
| full | afternoon_large20_two_sided_magnet | mid | 2457 | 162.21 | True | 1041 | 1416 |
| full | afternoon_large20_two_sided_magnet | strict | 2357 | 155.61 | True | 999 | 1358 |
| limited_core_window | morning_above_poc_signed_magnet_short | loose | 180 | 121.28 | True | 0 | 180 |
| limited_core_window | morning_above_poc_signed_magnet_short | mid | 171 | 115.22 | True | 0 | 171 |
| limited_core_window | morning_above_poc_signed_magnet_short | strict | 165 | 111.18 | True | 0 | 165 |
| limited_core_window | morning_below_poc_signed_magnet_long | loose | 168 | 113.2 | True | 168 | 0 |
| limited_core_window | morning_below_poc_signed_magnet_long | mid | 161 | 108.48 | True | 161 | 0 |
| limited_core_window | morning_below_poc_signed_magnet_long | strict | 151 | 101.74 | True | 151 | 0 |
| limited_core_window | late_morning_large10_two_sided_magnet | loose | 323 | 217.64 | True | 154 | 169 |
| limited_core_window | late_morning_large10_two_sided_magnet | mid | 309 | 208.2 | True | 150 | 159 |
| limited_core_window | late_morning_large10_two_sided_magnet | strict | 290 | 195.4 | True | 139 | 151 |
| limited_core_window | midday_signed_two_sided_magnet | loose | 303 | 204.16 | True | 141 | 162 |
| limited_core_window | midday_signed_two_sided_magnet | mid | 288 | 194.05 | True | 133 | 155 |
| limited_core_window | midday_signed_two_sided_magnet | strict | 275 | 185.29 | True | 127 | 148 |
| limited_core_window | afternoon_large20_two_sided_magnet | loose | 300 | 202.14 | True | 136 | 164 |
| limited_core_window | afternoon_large20_two_sided_magnet | mid | 280 | 188.66 | True | 126 | 154 |
| limited_core_window | afternoon_large20_two_sided_magnet | strict | 272 | 183.27 | True | 123 | 149 |

CSV: research_artifacts/es_prior_poc_orderflow_magnet_density_audit_20260620.csv

# es_high_semivariance_mes_trend_pullback_crowding Density Audit

Pre-PnL density screen for MES participation crowding trend-pullback signals filtered to upper-half prior downside-semivariance regimes. No paid data was downloaded.

## Reformulation Note

Fixed-time high-semivariance variants were rejected before PnL because every candidate fell below 50 trades/year in at least one required reference window. The active variants use the first qualifying completed-bar signal inside fixed windows, max one trade per day. The underlying mechanic remains MES crowding during a completed ES pullback, prior completed ES trend alignment, and lagged high downside-semivariance regime.

## Windows

- full: `2019-05-06` to `2026-06-09`
- limited_core: `2021-07-13` to `2022-03-28`
- wfa90: `2019-05-06` to `2025-09-22`
- latest1y: `2025-06-10` to `2026-06-09`

## Final Variants

| variant_id | entry_combo_count | full_min_tpy | limited_core_min_tpy | wfa90_min_tpy | latest1y_min_tpy | pass |
|---|---:|---:|---:|---:|---:|---|
| afternoon60_notional_high_downside_window_1530 | 6 | 73.16 | 110.42 | 73.80 | 52.18 | true |
| late_morning30_notional_high_downside_window_1230 | 6 | 74.43 | 117.50 | 75.06 | 54.19 | true |
| midday60_notional_high_downside_window_1430 | 6 | 74.43 | 116.09 | 75.06 | 53.18 | true |
| morning15_notional_high_downside_window_1130 | 6 | 76.41 | 117.50 | 76.94 | 55.19 | true |
| morning15_trade_high_downside_window_1130 | 6 | 78.38 | 121.75 | 77.72 | 65.22 | true |

Decision: APPROVE_FOR_AUTHORING_AND_TESTING. All five selected variants clear the 50 trades/year floor across all checked windows and all declared entry parameter corners.

Detail CSV: `research_artifacts/es_high_semivariance_mes_trend_pullback_crowding_density_screen_20260620.csv`
Summary CSV: `research_artifacts/es_high_semivariance_mes_trend_pullback_crowding_density_summary_20260620.csv`

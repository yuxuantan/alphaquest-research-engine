# es_pivot_filtered_vwap_pullback_continuation density audit

Purpose: pre-PnL density gate for final pivot-filtered VWAP variants.

Data source: `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`.

No paid data was downloaded or requested.

Rejected pre-PnL drafts: strict 2-of-2 5/15m pivot alignment, original sparse failed-break/midday/opening-drive clones. They were rejected before any PnL was inspected.

Active filter: carried completed 5/15m pivot state, `min_aligned_timeframes: 1`, and no opposite checked timeframe by implementation.

Windows mirror current runner defaults and each window starts with fresh strategy/pivot state:
- full_core: 2011-01-03 through 2026-06-09
- limited_core_random10: 2011-02-22 through 2012-09-06
- wfa_first90: 2011-01-03 through 2024-11-22
- latest_1y_reference: 2025-06-10 through 2026-06-09

Density decision: PASS

| variant | fixed full/y | fixed limited/y | fixed wfa90/y | fixed latest1y/y | all-pass entry combos | decision |
|---|---:|---:|---:|---:|---:|---|
| failed_vwap_break_two_sided_1500 | 84.8168 | 65.5244 | 82.0787 | 113.0774 | 9 | PASS |
| late_morning_trend_reclaim_two_sided_1300 | 79.374 | 73.3095 | 78.2627 | 87.0596 | 9 | PASS |
| midday_trend_reclaim_two_sided_1430 | 71.0154 | 54.4956 | 69.8389 | 79.0541 | 9 | PASS |
| morning_trend_reclaim_two_sided_1200 | 88.7693 | 84.3384 | 88.3425 | 93.0637 | 9 | PASS |
| opening_drive_pullback_two_sided_1400 | 84.2984 | 72.6607 | 83.0146 | 104.0712 | 9 | PASS |

This artifact counts entry signals only. It does not inspect PnL, grid profitability, WFA selections, or post-entry trade results.

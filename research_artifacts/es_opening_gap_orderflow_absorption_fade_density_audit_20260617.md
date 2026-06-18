# ES Opening Gap Orderflow Absorption Fade Density Audit

Date: 2026-06-17

Purpose: pre-PnL eligibility screen for a price-action plus aggregate-orderflow campaign. This audit checked raw signal frequency only. It did not inspect stops, targets, net profit, drawdown, WFA, or any performance result.

Data:
- Local Sierra aggregate orderflow cache only: `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
- Prepared through the repo data pipeline with `feature_set: pdh_pdl_sweep`
- Strategy timeframe: 5-minute RTH bars
- Date range: 2011-01-03 through 2026-06-09
- No network access or paid data download

Rejected formulations:
- Normal larger-gap grids such as 3-6 ES points were too sparse for the current methodology. Strict entry-grid corners were generally below 50 raw signals per year.
- A zero-gap formulation cleared density but was rejected before PnL because it no longer convincingly expressed an opening-gap edge.
- Signed-volume-only versions were rejected because their strict corners were too sparse or diluted relative to large-trade aggregate flow.

Approved entry grid for testing:
- `entry.params.min_opening_gap_ticks`: `[4, 8, 12]`
- `entry.params.min_orderflow_imbalance`: `[0.02, 0.05, 0.08]`

This is a 1-3 ES point nonzero opening-gap screen. It is broad, but still expresses the edge because every signal requires both a real prior RTH close-to-RTH open dislocation and completed aggregate orderflow against that gap.

Selected variants:

| Variant | Flow bucket | Source window ET | Min signals/year | Median signals/year | Max signals/year | Decision |
| --- | --- | --- | ---: | ---: | ---: | --- |
| early_large20_gap_absorption_fade_1000 | large20 | 09:45-10:00 | 61.83 | 80.62 | 104.08 | approve_for_testing |
| morning_large20_gap_absorption_fade_1030 | large20 | 10:00-10:30 | 59.62 | 79.45 | 106.35 | approve_for_testing |
| late_morning_large20_gap_absorption_fade_1100 | large20 | 10:45-11:00 | 64.48 | 82.82 | 102.20 | approve_for_testing |
| midday_large20_gap_absorption_fade_1200 | large20 | 11:30-12:00 | 60.59 | 81.72 | 105.57 | approve_for_testing |
| late_morning_large10_gap_absorption_fade_1100 | large10 | 10:45-11:00 | 54.76 | 77.06 | 104.86 | approve_for_testing |

Duplicate-edge decision:
- Not a plain `es_overnight_intraday_reversal` retest because it requires post-open completed aggregate-flow absorption before entry.
- Not `es_opening_drive_inventory_absorption` because the reference price-action condition is the prior-close-to-open gap, not an opening-drive return from the RTH open.
- Not `es_opening_range_orderflow_breakout` because it fades the gap on counter-gap flow instead of trading opening-range continuation.

Final pre-PnL decision: approve exactly five variants for staged testing.

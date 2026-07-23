# ES Wide-Range Orderflow Continuation Density Audit - 2026-06-18

This was performed before any PnL backtest for `es_wide_range_orderflow_continuation`.

Data: `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet` aggregated through the repo pipeline to 5-minute RTH bars with `feature_set: pdh_pdl_sweep` and `rolling_volume_window: 20`.

Default limited-core window resolved from the current benchmark policy: 2011-02-22 through 2012-09-06. The policy uses a random 10% contiguous period, avoids the latest 10% of available data, and avoids the configured COVID range.

Declared entry grid: `entry.params.min_range_ticks: [4, 8, 12]` and `entry.params.min_orderflow_imbalance: [0.0, 0.02, 0.04]`. Stop and target grids do not affect signal density.

Strict-corner results:

| Variant | Full strict signals/year | Limited-core strict signals/year |
| --- | ---: | ---: |
| morning_signed_range_expansion_long | 141.32 | 126.51 |
| morning_signed_range_expansion_short | 143.91 | 125.86 |
| midday_large10_range_expansion_twosided | 158.16 | 106.40 |
| afternoon_large20_range_expansion_long | 127.06 | 77.20 |
| afternoon_large20_range_expansion_short | 122.14 | 67.47 |

Conclusion: all five variants clear the 50 trades/year feasibility floor at the strictest declared entry-grid corner in both full history and the current default limited-core window. This is a density check only, not evidence of profitability.

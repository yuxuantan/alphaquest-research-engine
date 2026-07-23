# NQ Leveraged ETF Rebalance Pressure Density Audit

Decision: PASS

This is a pre-PnL density audit. It counts only the completed NQ return from the prior RTH close, and for late-acceleration variants the completed recent return window at the declared signal time. It does not inspect stops, targets, trade PnL, WFA, Monte Carlo, or holdout outcomes.

- Bars: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`
- Feature availability: prior RTH close is known before the session; the signal uses the completed one-minute bar whose close equals the configured signal time.
- Test window for density: 2011-01-03 through 2026-06-12.
- Span years: 15.44.
- Grid counted: entry-side `min_abs_day_return_bps`; for late acceleration, also `min_recent_return_bps`.

| Variant | Entry combos | Min candidates | Max candidates | Min/year | Max/year |
|---|---:|---:|---:|---:|---:|
| down_day_rebalance_short_1500 | 3 | 959 | 1088 | 62.11 | 70.46 |
| late_acceleration_two_sided_1530 | 9 | 1287 | 1597 | 83.35 | 103.42 |
| two_sided_day_move_1430 | 3 | 1867 | 2357 | 120.91 | 152.64 |
| two_sided_day_move_1500 | 3 | 2123 | 2701 | 137.49 | 174.92 |
| up_day_rebalance_long_1500 | 3 | 1452 | 1628 | 94.03 | 105.43 |

All variants have enough pre-PnL signal density to justify staged testing.

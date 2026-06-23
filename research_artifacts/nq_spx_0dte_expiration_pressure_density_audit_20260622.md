# NQ SPX 0DTE Expiration Pressure Density Audit

Decision: PASS

This is a pre-PnL density audit. It counts only ex-ante SPX 0DTE calendar membership and completed NQ open-to-signal move thresholds. It does not inspect stops, targets, trade PnL, WFA, Monte Carlo, or holdout outcomes.

- Bars: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`
- Calendar: `data/external/nq_spx_0dte_calendar_sessions_20110103_20260612.csv`
- Availability: SPX 0DTE listing membership is known before the session; NQ move uses only the current RTH open and completed signal-bar close.
- Standard monthly OPEX Fridays are excluded.
- Density window: 2022-05-11 through 2026-06-12.

| Variant | Entry combos | Min candidates | Max candidates | Min/year | Max/year |
|---|---:|---:|---:|---:|---:|
| full_week_down_move_fade_long_1000 | 3 | 286 | 368 | 69.92 | 89.97 |
| full_week_late_move_continuation_1430 | 3 | 665 | 772 | 162.58 | 188.74 |
| full_week_up_move_fade_short_1000 | 3 | 333 | 428 | 81.41 | 104.64 |
| mwf_two_sided_fade_1030 | 3 | 360 | 456 | 88.01 | 111.48 |
| tue_thu_two_sided_fade_1030 | 3 | 285 | 347 | 69.68 | 84.83 |

All variants and declared entry corners clear the 50 candidate-session/year opportunity threshold before PnL testing.

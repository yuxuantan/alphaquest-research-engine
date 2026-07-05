# NQ RTH Intraday Risk Premium Density Audit

Generated on 2026-06-30 before any NQ PnL testing for `nq_rth_intraday_risk_premium`.

Input: cleaned and aggregated 5-minute NQ RTH bars from `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet` via `propstack.data.pipeline.prepare_data`.

Availability rule: signal time is fixed before the session, and a signal can emit only after the configured completed 5-minute RTH bar closes. Weekday is known before the session. No return outcome, future high/low, final VWAP, or PnL data is used.

Full window: 2011-01-03 to 2026-06-12, 3813 sessions.
Limited-core density window: 2011-02-22 to 2012-09-07, 371 sessions.
Latest window: 2025-06-09 to 2026-06-12, 252 sessions.

| Variant | Signal time | Full signals/year | Limited-core signals/year | Latest 252-session signals | Decision |
|---|---:|---:|---:|---:|---|
| early_afternoon_1300_long | 13:00:00 | 246.93 | 240.26 | 252 | PASS |
| first_hour_1000_long | 10:00:00 | 246.93 | 240.26 | 252 | PASS |
| late_morning_1100_long | 11:00:00 | 246.93 | 240.26 | 252 | PASS |
| midmorning_1030_long | 10:30:00 | 246.93 | 240.26 | 252 | PASS |
| open_0935_long | 09:35:00 | 246.93 | 240.26 | 252 | PASS |

Decision: PASS. 5/5 fixed entry rows cleared the density gate. Minimum full-history density was 246.93 signals/year; minimum limited-core density was 240.26 signals/year; minimum latest-window count was 252.

No PnL, trade outcome, or parameter selection data was inspected during this screen.

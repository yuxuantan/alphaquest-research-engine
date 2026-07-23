# NQ Intraday Capitulation Mean Reversion Density Audit

Pre-PnL signal-density screen. Counts are sessions with at least one completed-bar signal for each entry-parameter corner; no trade PnL or post-entry outcome was inspected.

- Data: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`
- Date range: 2011-01-03 to 2026-06-12
- Full-history years: 15.4387
- Latest-session screen starts: 2025-06-09

| variant | min full signals/year | min latest252 signals | decision |
|---|---:|---:|---|
| afternoon_5m_fast_liquidation_snapback_long_1530 | 12.18 | 0 | FAIL_DENSITY |
| full_session_30m_structural_flush_reclaim_long_1530 | 0.91 | 0 | FAIL_DENSITY |
| midday_15m_vwap_dislocation_reclaim_long_1430 | 3.95 | 0 | FAIL_DENSITY |
| morning_15m_sell_capitulation_reclaim_long_1200 | 0.32 | 0 | FAIL_DENSITY |
| opening_5m_sell_capitulation_reclaim_long_1030 | 1.75 | 0 | FAIL_DENSITY |

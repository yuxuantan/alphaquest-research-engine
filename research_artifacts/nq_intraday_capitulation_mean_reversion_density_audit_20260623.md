# NQ Intraday Capitulation Mean Reversion Density Audit

Pre-PnL signal-density screen after correcting the runner feature path (`data.feature_set: intraday_capitulation_mr`). Counts use the same prepared bars consumed by staged tests and count sessions with at least one completed-bar signal for each declared entry-parameter corner; no trade PnL or post-entry outcome was inspected.

- Date range: 2011-01-03 to 2026-06-12
- Full-history years: 15.4387
- Latest-session screen starts: 2025-06-09

| variant | min full signals/year | min latest252 signals | decision |
|---|---:|---:|---|
| afternoon_15m_liquidation_snapback_long_1530 | 68.40 | 60 | PASS_DENSITY |
| full_session_15m_structural_flush_reclaim_long_1530 | 69.31 | 59 | PASS_DENSITY |
| midday_15m_vwap_flush_reclaim_long_1430 | 57.06 | 52 | PASS_DENSITY |
| morning_10m_volume_flush_reclaim_long_1230 | 59.53 | 63 | PASS_DENSITY |
| opening_5m_volume_flush_reclaim_long_1100 | 65.55 | 61 | PASS_DENSITY |

# NQ Pre-Holiday Effect Density Audit

Generated on 2026-06-30 before any NQ PnL testing for `nq_preholiday_effect`.

Input: completed 1-minute NQ RTH bars from `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet` via `propstack.data.pipeline.prepare_data`, plus deterministic signal dates from `data/external/nyse_preholiday_regular_sessions_20110103_20260609.csv`.

Availability rule: signal dates are the final regular RTH session before a full NYSE holiday; momentum/range filters use only completed same-session bars through the configured entry bar. No return, PnL, future high/low, or holiday-window outcome was inspected.

Sparse-event density gate: full-history signals/year >= 5, limited-core proxy signals/year >= 5, and latest-252-session signal count >= 5.
Full window: 2011-01-03 to 2026-06-09, 3810 sessions, 15.43 years.
Limited-core density proxy window: 2011-02-22 to 2012-09-06, 370 sessions, 1.54 years.
Latest window: 2025-06-04 to 2026-06-09, 252 sessions.

| Variant | Setup | Entry time | Entry param | Value | Full/year | Limited/year | Latest signals | Decision |
|---|---|---:|---|---:|---:|---:|---:|---|
| preholiday_late_long_1500 | unconditional_long | 15:00:00 | none | fixed | 9.20 | 7.79 | 10 | PASS |
| preholiday_low_range_midday_long_1200 | low_range_long | 12:00:00 | entry.params.max_session_range_bps | 35.0 | 0.39 | 0.00 | 0 | FAIL |
| preholiday_low_range_midday_long_1200 | low_range_long | 12:00:00 | entry.params.max_session_range_bps | 55.0 | 2.66 | 1.95 | 0 | FAIL |
| preholiday_low_range_midday_long_1200 | low_range_long | 12:00:00 | entry.params.max_session_range_bps | 75.0 | 4.15 | 2.60 | 2 | FAIL |
| preholiday_midday_long_1200 | unconditional_long | 12:00:00 | none | fixed | 9.20 | 7.79 | 10 | PASS |
| preholiday_momentum_confirmed_midday_long_1200 | momentum_confirmed_long | 12:00:00 | entry.params.min_session_return_bps | 0.0 | 5.38 | 3.24 | 7 | FAIL |
| preholiday_momentum_confirmed_midday_long_1200 | momentum_confirmed_long | 12:00:00 | entry.params.min_session_return_bps | 10.0 | 4.47 | 3.24 | 7 | FAIL |
| preholiday_momentum_confirmed_midday_long_1200 | momentum_confirmed_long | 12:00:00 | entry.params.min_session_return_bps | 20.0 | 3.69 | 3.24 | 7 | FAIL |
| preholiday_open_long_1000 | unconditional_long | 10:00:00 | none | fixed | 9.20 | 7.79 | 10 | PASS |

Decision: FAIL. 3/9 declared entry rows cleared the sparse-event density gates.

Minimum full-history density: 0.39 signals/year. Minimum limited-core density: 0.00 signals/year. Minimum latest-window count: 0.

No return, PnL, trade outcome, stop, target, or equity data was inspected during this screen.

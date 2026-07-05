# NQ Quarterly Expiration Pressure Event/Data-Quality Audit

Review date: 2026-06-30

Scope: pre-PnL sparse-event audit for `nq_quarterly_expiration_pressure` before staged PnL.

Data: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`
Window: 2011-01-03 through 2026-06-12

Gate: each expected deterministic event must have the completed signal bar and next entry bar in the NQ RTH cache. No PnL is inspected in this audit.

| variant_id | expected_events | available_signal_bars | available_entry_bars | missing_signal_bars | missing_entry_bars | full_events_per_year | latest_252_session_events | pass_data_quality_gate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| expiration_friday_midday_long_1200 | 61 | 61 | 61 | 0 | 0 | 3.951099 | 4 | True |
| expiration_friday_open_short_1000 | 61 | 61 | 61 | 0 | 0 | 3.951099 | 4 | True |
| monday_after_expiration_reversal_long_1000 | 61 | 57 | 57 | 4 | 4 | 3.692011 | 4 | False |
| monday_prior_roll_week_long_1000 | 61 | 52 | 52 | 9 | 9 | 3.36815 | 4 | False |
| thursday_prior_positioning_short_1330 | 61 | 60 | 60 | 1 | 1 | 3.886327 | 3 | False |

Conclusion: FAIL.
At least one variant is missing an expected event signal or entry bar. Staged PnL should not proceed until the data gate is resolved.

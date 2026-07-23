# Event-Density Audit: nq_vix_expiration_pressure

Date: 2026-06-30

Verdict: FAIL.

This is a pre-PnL calendar-event audit. VIX settlement variants are intentionally low-frequency, so the generic 50-signals/year screen is not used as a rejection rule here. The staged runner will evaluate trade count, benchmark adjustments, WFA stability, Monte Carlo, prop rules, and concentration.

- Calendar: `data/external/vix_expiration_sessions_20110103_20260609.csv`
- NQ signal-time bar availability cache: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`
- Full window: 2011-01-03 through 2026-06-12
- Event-density gate used here: configured `benchmarks.min_trades_per_year >= 5` and zero missing signal-time bars.

| variant | signal type | signal time | direction | calendar events | available signal bars | missing signal bars | events/year | latest 365d events |
|---|---|---:|---|---:|---:|---:|---:|---:|
| post_vix_settlement_next_session_long_1000 | next_regular_session | 10:00:00 | long | 185 | 184 | 1 | 11.9828 | 12 |
| prior_session_late_hedge_unwind_long_1500 | previous_regular_session | 15:00:00 | long | 185 | 182 | 3 | 11.9828 | 12 |
| vix_settlement_late_reversal_long_1500 | vix_expiration_session | 15:00:00 | long | 185 | 182 | 3 | 11.9828 | 12 |
| vix_settlement_midday_reversal_long_1200 | vix_expiration_session | 12:00:00 | long | 185 | 182 | 3 | 11.9828 | 12 |
| vix_settlement_open_pressure_short_1000 | vix_expiration_session | 10:00:00 | short | 185 | 182 | 3 | 11.9828 | 12 |

Missing NQ cache sessions at configured signal-bar times:

- `post_vix_settlement_next_session_long_1000`: 2011-04-21
- `prior_session_late_hedge_unwind_long_1500`: 2011-03-15, 2011-10-18, 2014-03-17
- `vix_settlement_late_reversal_long_1500`: 2011-02-16, 2011-10-19, 2020-03-18
- `vix_settlement_midday_reversal_long_1200`: 2011-02-16, 2011-10-19, 2020-03-18
- `vix_settlement_open_pressure_short_1000`: 2011-02-16, 2011-10-19, 2020-03-18

Data-quality decision: FAIL before staged PnL. The missing event sessions include a 2020 VIX settlement date, so silently skipping them would make the event sample ambiguous.

# Event-Density Audit: nq_bls_macro_release_day_drift

Date: 2026-06-30

Verdict: FAIL.

This is a pre-PnL signal-density audit. Counts use only public BLS release dates and completed NQ RTH bars up to the configured signal time. No release values, surprises, revisions, PnL, stops, targets, or future session outcomes are inspected.

- Calendar: `data/external/bls_macro_release_dates_20110103_20260609.csv`
- NQ bar cache: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`
- Full window: 2011-01-03 through 2026-06-12
- Density gate used here: no missing signal-time bars, at least configured 5 signals/year, and at least 5 signals in the latest 365-day window for every declared entry-filter row.

| variant | setup | release types | entry time | entry param | calendar dates | available bars | missing bars | signals | signals/year | latest 365d signals | pass |
|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| combined_bls_release_low_range_long_1200 | low_range_long | cpi,employment_situation | 12:00:00 | entry.params.max_session_range_bps=20 | 386 | 374 | 12 | 1 | 0.0648 | 0 | False |
| combined_bls_release_low_range_long_1200 | low_range_long | cpi,employment_situation | 12:00:00 | entry.params.max_session_range_bps=35 | 386 | 374 | 12 | 9 | 0.5829 | 0 | False |
| combined_bls_release_low_range_long_1200 | low_range_long | cpi,employment_situation | 12:00:00 | entry.params.max_session_range_bps=50 | 386 | 374 | 12 | 44 | 2.8500 | 1 | False |
| combined_bls_release_momentum_long_1130 | momentum_confirmed_long | cpi,employment_situation | 11:30:00 | entry.params.min_session_return_bps=0 | 386 | 374 | 12 | 208 | 13.4726 | 10 | False |
| combined_bls_release_momentum_long_1130 | momentum_confirmed_long | cpi,employment_situation | 11:30:00 | entry.params.min_session_return_bps=10 | 386 | 374 | 12 | 181 | 11.7238 | 9 | False |
| combined_bls_release_momentum_long_1130 | momentum_confirmed_long | cpi,employment_situation | 11:30:00 | entry.params.min_session_return_bps=20 | 386 | 374 | 12 | 150 | 9.7158 | 8 | False |
| combined_bls_release_open_long_1000 | unconditional_long | cpi,employment_situation | 10:00:00 | none | 386 | 374 | 12 | 374 | 24.2248 | 19 | False |
| cpi_release_open_long_1000 | unconditional_long | cpi | 10:00:00 | none | 196 | 193 | 3 | 193 | 12.5010 | 10 | False |
| employment_release_open_long_1000 | unconditional_long | employment_situation | 10:00:00 | none | 190 | 181 | 9 | 181 | 11.7238 | 9 | False |

Missing NQ cache sessions at configured signal-bar times:

- `combined_bls_release_low_range_long_1200`: 2011-10-19, 2012-03-09, 2012-04-06, 2012-07-06, 2014-07-03, 2015-04-03, 2017-04-14, 2020-04-10, 2021-04-02, 2023-04-07, 2025-07-03, 2026-04-03
- `combined_bls_release_momentum_long_1130`: 2011-10-19, 2012-03-09, 2012-04-06, 2012-07-06, 2014-07-03, 2015-04-03, 2017-04-14, 2020-04-10, 2021-04-02, 2023-04-07, 2025-07-03, 2026-04-03
- `combined_bls_release_open_long_1000`: 2011-10-19, 2012-03-09, 2012-04-06, 2012-07-06, 2014-07-03, 2015-04-03, 2017-04-14, 2020-04-10, 2021-04-02, 2023-04-07, 2025-07-03, 2026-04-03
- `cpi_release_open_long_1000`: 2011-10-19, 2017-04-14, 2020-04-10
- `employment_release_open_long_1000`: 2012-03-09, 2012-04-06, 2012-07-06, 2014-07-03, 2015-04-03, 2021-04-02, 2023-04-07, 2025-07-03, 2026-04-03

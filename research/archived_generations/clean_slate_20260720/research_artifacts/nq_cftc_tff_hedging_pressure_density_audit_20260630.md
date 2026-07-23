# NQ CFTC TFF Hedging Pressure Density Audit

Generated on 2026-06-30 before any NQ PnL testing for `nq_cftc_tff_hedging_pressure`.

Input: completed 5-minute NQ RTH bars from `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet` via `propstack.data.pipeline.prepare_data`, plus shifted local CFTC/TFF feature file `data/external/cftc_tff_hedging_pressure_features.csv`.

Availability rule: CFTC Tuesday TFF positions are consumed only from the shifted `trade_date` rows in the local feature file; a session can count only when the configured completed entry bar exists and the session date has a finite shifted feature value crossing the declared threshold.

Full window: 2013-04-15 to 2026-06-12, 3270 sessions, 13.16 years.
Limited-core density proxy window: 2013-06-04 to 2014-09-26, 322 sessions, 1.31 years. This mirrors the staged random-fraction shortlist window from the configured post-feature range.
Latest window: 2025-06-09 to 2026-06-12, 252 sessions.

| Variant | Direction | Entry time | Operator | Threshold | Full/year | Limited/year | Latest signals | Decision |
|---|---|---:|---:|---:|---:|---:|---:|---|
| broad_negative_pressure_short_1100 | short | 11:00:00 | <= | -100000.0 | 26.59 | 0.00 | 107 | FAIL |
| broad_negative_pressure_short_1100 | short | 11:00:00 | <= | -50000.0 | 49.08 | 29.68 | 116 | FAIL |
| broad_negative_pressure_short_1100 | short | 11:00:00 | <= | -25000.0 | 79.02 | 70.01 | 126 | PASS |
| broad_positive_pressure_long_1100 | long | 11:00:00 | >= | 25000.0 | 66.41 | 39.57 | 96 | FAIL |
| broad_positive_pressure_long_1100 | long | 11:00:00 | >= | 47442.0 | 49.62 | 14.46 | 76 | FAIL |
| broad_positive_pressure_long_1100 | long | 11:00:00 | >= | 75000.0 | 30.39 | 3.80 | 66 | FAIL |
| extreme_negative_pressure_short_1330 | short | 13:30:00 | <= | -250000.0 | 11.17 | 0.00 | 43 | FAIL |
| extreme_negative_pressure_short_1330 | short | 13:30:00 | <= | -150000.0 | 17.93 | 0.00 | 99 | FAIL |
| extreme_negative_pressure_short_1330 | short | 13:30:00 | <= | -75000.0 | 34.50 | 3.80 | 116 | FAIL |
| extreme_positive_pressure_long_1330 | long | 13:30:00 | >= | 125000.0 | 19.98 | 0.00 | 51 | FAIL |
| extreme_positive_pressure_long_1330 | long | 13:30:00 | >= | 175000.0 | 18.84 | 0.00 | 46 | FAIL |
| extreme_positive_pressure_long_1330 | long | 13:30:00 | >= | 250000.0 | 16.56 | 0.00 | 39 | FAIL |
| high_positive_pressure_long_0935 | long | 09:35:00 | >= | 75000.0 | 30.39 | 3.80 | 66 | FAIL |
| high_positive_pressure_long_0935 | long | 09:35:00 | >= | 98748.0 | 24.77 | 3.80 | 61 | FAIL |
| high_positive_pressure_long_0935 | long | 09:35:00 | >= | 150000.0 | 19.22 | 0.00 | 51 | FAIL |

Decision: FAIL. 1/15 declared entry rows cleared the full-history, limited-core, and latest-window density gates.

Minimum full-history density: 11.17 signals/year. Minimum limited-core density: 0.00 signals/year. Minimum latest-window count: 39.

No return, PnL, trade outcome, stop, target, or equity data was inspected during this screen.

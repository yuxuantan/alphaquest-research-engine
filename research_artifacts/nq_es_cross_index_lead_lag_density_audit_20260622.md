# NQ ES Cross-Index Lead-Lag Density Audit

Decision: PASS

This is a pre-PnL density audit. It counts only completed ES and NQ rolling-return conditions at each declared signal time. It does not inspect stops, targets, trade PnL, WFA, Monte Carlo, or holdout outcomes.

- Bars: `data/cache/orderflow/nq_es_lead_lag_1m_20110103_20260609_full_rth_ny.parquet`
- Availability: each signal uses completed same-session ES and NQ return windows ending at the configured signal timestamp.
- Entry timing: next NQ bar open or later after the signal bar close.
- Test window for density: 2011-01-03 through 2026-06-09.
- Span years: 15.43.

| Variant | Entry combos | Min candidates | Max candidates | Min/year | Max/year |
|---|---:|---:|---:|---:|---:|
| early15_two_sided_lag_follow_1030 | 6 | 838 | 1190 | 54.30 | 77.11 |
| early30_two_sided_lag_follow_1000 | 9 | 1179 | 1463 | 76.39 | 94.80 |
| late_day30_confirmed_lag_follow_1530 | 4 | 827 | 1061 | 53.59 | 68.75 |
| late_morning60_two_sided_lag_follow_1130 | 9 | 1023 | 1318 | 66.29 | 85.40 |
| midday60_confirmed_lag_follow_1230 | 4 | 862 | 1010 | 55.85 | 65.44 |

All variants and declared entry corners clear the 50 candidate-session/year opportunity threshold before PnL testing.

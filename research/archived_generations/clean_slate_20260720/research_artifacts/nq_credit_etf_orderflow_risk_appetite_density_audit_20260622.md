# NQ Credit ETF Orderflow Risk-Appetite Density Audit

Decision: PASS_WITH_SPARSE_STRICT_CORNERS

This is a pre-PnL density audit. It counts only lagged HYG rank state, completed NQ open-to-signal movement, and completed aggregate signed-flow confirmation at the declared 5-minute signal times. It does not inspect stops, targets, trade PnL, WFA, Monte Carlo, or holdout outcomes.

- Bars: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`
- Features: `data/external/nq_credit_etf_risk_appetite_features_20110103_20260612.csv`
- Feature availability: latest ETF daily close strictly before NQ session_date.
- Signal times: 10:00, 10:30, 11:30, 12:30 ET.
- Grid counted: rank_threshold in 0.65/0.70/0.75 and min_orderflow_imbalance in 0.00/0.01/0.02.

| Variant | Min candidates | Max candidates | Min/year | Max/year |
|---|---:|---:|---:|---:|
| hyg_1d_strength_signed_long_1230 | 294 | 778 | 19.04 | 50.39 |
| hyg_1d_two_sided_signed_1230 | 569 | 1554 | 36.86 | 100.66 |
| hyg_1d_weakness_signed_short_1230 | 275 | 776 | 17.81 | 50.26 |
| hyg_3d_two_sided_signed_1230 | 515 | 1486 | 33.36 | 96.25 |
| hyg_5d_two_sided_signed_1230 | 529 | 1535 | 34.26 | 99.43 |

The one-sided variants have sparse strict corners, but their broader declared thresholds reach about 50 candidate sessions per year. The two-sided variants are comfortably dense. Proceed to staged testing with fail-closed trade-count gates.

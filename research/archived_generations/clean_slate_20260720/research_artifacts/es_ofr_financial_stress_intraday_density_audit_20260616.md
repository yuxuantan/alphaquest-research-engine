# ES OFR Financial Stress Intraday Density Audit - 2026-06-16

Scope: pre-performance density screen for `es_ofr_financial_stress_intraday`.

Data:

- ES RTH bars: `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
- OFR FSI source cache: `data/external/ofr_financial_stress_index_2000_2026.csv`
- Derived feature file: `data/external/es_ofr_financial_stress_features_20110103_20260609.csv`
- Feature rule: each ES session receives the latest OFR observation on or before `session_date - 2 business days`, matching OFR's stated publication lag.
- Rows: 3817
- Valid rank rows: 3760
- Session range: 2011-01-03 through 2026-06-09

Planned entry-threshold density:

| Variant | Feature | Thresholds | Min signals | Min trades/year |
| --- | --- | --- | ---: | ---: |
| `rising_global_stress_short_1000` | `ofr_fsi_change_1d_rank_252` | 0.55, 0.60, 0.65 | 1356 | 87.88 |
| `high_credit_stress_short_1030` | `credit_rank_252` | 0.55, 0.60, 0.65 | 1216 | 78.80 |
| `funding_stress_short_1130` | `funding_rank_252` | 0.55, 0.60, 0.65 | 1415 | 91.70 |
| `us_stress_short_1200` | `united_states_rank_252` | 0.55, 0.60, 0.65 | 1254 | 81.27 |
| `volatility_stress_short_1330` | `volatility_rank_252` | 0.55, 0.60, 0.65 | 1335 | 86.52 |

Decision: proceed to preflight and staged testing. No performance results were inspected before locking this parameter space.

# ES FINRA Margin Leverage Density Audit - 2026-06-17

Purpose: pre-PnL density check for the `es_finra_margin_leverage` campaign.

Data:

- ES local Sierra RTH cache:
  `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
- Official free FINRA margin statistics cache:
  `data/external/finra_margin_statistics.xlsx`
- Derived feature file:
  `data/external/es_finra_margin_leverage_features_20110103_20260609.csv`

Feature availability rule:

- FINRA observations are monthly and are mapped to ES sessions only after a
  35-calendar-day lag from month-end.
- This is intentionally conservative to avoid release-date lookahead.

Feature coverage:

- Session rows: `3817`
- Rank-complete rows: `3295`
- Session span: `2011-01-03` through `2026-06-09`

Predeclared variant density:

| variant | feature/rule | threshold grid | min signals/year |
|---|---|---:|---:|
| `rapid_margin_1m_expansion_short_1030` | `margin_debt_change_1m_rank_120m >= threshold` | `0.60, 0.70, 0.75` | `55.09` |
| `rapid_margin_3m_expansion_short_1130` | `margin_debt_change_3m_rank_120m >= threshold` | `0.55, 0.65, 0.75` | `50.74` |
| `persistent_margin_12m_expansion_short_1200` | `margin_debt_change_12m_rank_120m >= threshold` | `0.55, 0.65, 0.72` | `51.13` |
| `debit_credit_ratio_expansion_short_1330` | `debit_credit_ratio_change_3m_rank_120m >= threshold` | `0.60, 0.70, 0.75` | `58.78` |
| `margin_deleveraging_rebound_long_1430` | `margin_debt_change_3m_rank_120m <= threshold` | `0.25, 0.30, 0.35` | `50.81` |

Decision: PASS density screen. The campaign is eligible for staged testing.

# NQ Default-Spread Orderflow Risk-Premium Density Audit - 2026-06-23

Decision: FAIL before NQ PnL inspection.

This screen used the repo data-prep path on completed NQ RTH bars and counted only signal availability for the declared entry-grid corners. It did not inspect trade outcomes, stops, targets, WFA, Monte Carlo, or final holdout performance.

## Data

- NQ source: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`
- Prepared timeframe: 5-minute bars, America/New_York RTH.
- Credit source: local FRED Moody's Aaa/Baa yield CSVs.
- Feature output: `data/external/nq_default_spread_features_20110103_20260612.csv`.
- Availability rule: latest Aaa/Baa observation on or before session date minus two business days.
- Prepared bars: 297,414; sessions: 3,813; period: 2011-01-03 through 2026-06-12; latest-252 window: 2025-06-09 through 2026-06-12.

## Density Results

| variant | entry combos | min full signals/year | max full signals/year | min latest252 signals | max latest252 signals | density pass | weakest entry params |
|---|---:|---:|---:|---:|---:|---|---|
| `high_spread_large10_long_1230` | 9 | 29.4713 | 37.8269 | 0 | 2 | FAIL | credit_rank_threshold=0.62; min_orderflow_imbalance=0.08 |
| `high_spread_signed_long_1230` | 9 | 3.7568 | 25.9088 | 0 | 0 | FAIL | credit_rank_threshold=0.62; min_orderflow_imbalance=0.06 |
| `tightening_spread_signed_long_1130` | 9 | 11.7885 | 65.6142 | 6 | 66 | FAIL | credit_rank_threshold=0.6; min_orderflow_imbalance=0.04 |
| `two_sided_spread_change_large10_1130` | 9 | 56.1574 | 84.2038 | 67 | 98 | PASS | credit_rank_threshold=0.7; min_orderflow_imbalance=0.06 |
| `widening_spread_signed_short_1230` | 9 | 7.1897 | 51.2995 | 4 | 60 | FAIL | credit_rank_threshold=0.7; min_orderflow_imbalance=0.04 |

Only `two_sided_spread_change_large10_1130` cleared both the >=50 full-history signals/year screen and the >=50 latest-252-session screen across declared entry-grid corners. A one-variant subset is not a valid campaign under the five-variant campaign policy, so no staged PnL testing was run.

## Rejection Notes

- The high default-spread long variants generated zero latest-252 signals at all declared entry-grid corners, indicating that the ES high-spread state did not provide current NQ opportunity density.
- Tightening-spread and widening-spread variants had insufficient strict-corner density despite some looser corners crossing the threshold.
- No NQ rescue was authorized and no NQ PnL was inspected, so the proper action is fail-closed rejection rather than parameter surgery.

Detailed CSV: `research_artifacts/nq_default_spread_orderflow_risk_premium_density_audit_20260623.csv`

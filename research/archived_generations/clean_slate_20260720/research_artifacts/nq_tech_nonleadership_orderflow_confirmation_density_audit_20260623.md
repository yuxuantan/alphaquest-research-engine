# NQ Tech Non-Leadership Orderflow Confirmation Density Audit

Generated on 2026-06-23 before any PnL testing for `nq_tech_nonleadership_orderflow_confirmation`.

Feature file: `data/external/nq_tech_relative_strength_features_20110103_20260612.csv`

Bar cache: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`

Availability rule: each NQ session uses only XLK and SPY observations available on or before `session_date - 1 business day`. Current-session confirmation uses only completed RTH NQ bars through the configured signal-bar close; entry is no earlier than the next bar.

Parameter-density screen: `rank_max in [0.60, 0.55, 0.50]`, `min_orderflow_imbalance in [0.0, 0.0025, 0.005]`, fixed short-side price tolerance `-8` ticks against the trade. No stop, target, or PnL data was inspected.

| Variant | Driver | Confirmation | Flow | Signals range | Signals/year range | Min calendar-year signals | Latest-year min signals |
|---|---|---|---|---:|---:|---:|---:|
| tech1d_nonleadership_1130_signed_flow_short | xlk_minus_spy_1d_rank_252 <= rank_max | return_and_flow at 11:30:00 | signed_imbalance | 559-799 | 34.94-49.94 | 9 | 9 |
| tech5d_nonleadership_1030_signed_flow_short | xlk_minus_spy_5d_rank_252 <= rank_max | return_and_flow at 10:30:00 | signed_imbalance | 572-812 | 35.75-50.75 | 14 | 14 |
| tech5d_nonleadership_1130_signed_flow_short | xlk_minus_spy_5d_rank_252 <= rank_max | return_and_flow at 11:30:00 | signed_imbalance | 538-813 | 33.62-50.81 | 10 | 10 |
| tech5d_nonleadership_1130_vwap_signed_short | xlk_minus_spy_5d_rank_252 <= rank_max | vwap_pressure at 11:30:00 | signed_imbalance | 514-780 | 32.12-48.75 | 10 | 10 |
| tech5d_nonleadership_1200_signed_flow_short | xlk_minus_spy_5d_rank_252 <= rank_max | return_and_flow at 12:00:00 | signed_imbalance | 511-780 | 31.94-48.75 | 9 | 9 |

Decision: approve for authoring. The broad rank threshold is labelled non-leadership rather than lower-tail weakness because `rank_max=0.60` is included for trade-density viability.

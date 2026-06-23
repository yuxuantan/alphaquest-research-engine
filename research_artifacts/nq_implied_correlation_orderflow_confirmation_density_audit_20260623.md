# NQ Implied-Correlation Orderflow Confirmation Density Audit

Generated on 2026-06-23 before PnL testing for `nq_implied_correlation_orderflow_confirmation`.

Feature file: `data/external/nq_cboe_implied_correlation_features_20110103_20260612.csv`

Bar cache: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`

Availability rule: Cboe COR1M/COR3M observations are strictly lagged before the NQ session date. Current-session flow confirmation uses completed RTH bars through the configured signal-bar close.

Parameter-density screen: rank threshold in `[0.55, 0.60, 0.65]`, `min_orderflow_imbalance in [0.0, 0.0025, 0.005]`. No PnL, stops, targets, or fills inspected.

| Variant | Driver | Flow | Signals range | Signals/year range | Min calendar-year signals | Latest-year min signals |
|---|---|---|---:|---:|---:|---:|
| rising_corr_1330_large20_flow_short | cor3m_change_1d_rank_252 >= rank_min at 13:30:00 | large20_imbalance | 687-900 | 42.94-56.25 | 17 | 17 |
| rising_corr_1330_signed_flow_short | cor3m_change_1d_rank_252 >= rank_min at 13:30:00 | signed_imbalance | 502-898 | 31.38-56.12 | 11 | 11 |
| shortterm_corr_1200_signed_flow_short | cor1m_minus_cor3m_rank_252 >= rank_min at 12:00:00 | signed_imbalance | 494-858 | 30.88-53.62 | 8 | 8 |
| shortterm_corr_1330_large20_flow_short | cor1m_minus_cor3m_rank_252 >= rank_min at 13:30:00 | large20_imbalance | 675-900 | 42.19-56.25 | 12 | 12 |
| shortterm_corr_1330_signed_flow_short | cor1m_minus_cor3m_rank_252 >= rank_min at 13:30:00 | signed_imbalance | 472-882 | 29.50-55.12 | 9 | 10 |

Decision: approve for authoring. Trade-count gate is set to 35 trades/year from density before PnL because signed-flow variants span roughly 30-55 signals/year while large-20 variants span roughly 42-56 signals/year.

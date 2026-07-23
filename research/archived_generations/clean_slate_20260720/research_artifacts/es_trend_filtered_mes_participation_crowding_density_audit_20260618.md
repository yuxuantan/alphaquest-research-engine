# es_trend_filtered_mes_participation_crowding Pre-PnL Density Audit

Date: 2026-06-18

Data: `data/cache/orderflow/es_mes_participation_crowding_1m_20190506_20260609_full_rth_ny.csv`. No external or paid data was downloaded.

Scope: signal-count audit before any PnL, fill, stop, target, WFA, monkey, or Monte Carlo result was inspected for this campaign.

Method: for each selected variant, count fixed-time completed-bar signals across the declared entry grid. A long signal requires high MES participation during a completed ES down-pullback and a prior completed ES uptrend window. A short signal requires high MES participation during a completed ES up-pullback and a prior completed ES downtrend window.

Entry grid: `share_rank_min=[0.45, 0.55, 0.6]`, `min_abs_return_ticks=[2, 4, 6]`. Stop and target grids are excluded from signal counts because they do not affect entry density.

| Variant | Min signals/year | Max signals/year | Decision |
|---|---:|---:|---|
| `afternoon_notional_trend_pullback_reversal_1400` | 51.0 | 67.8 | approve_for_testing |
| `early_afternoon_notional_trend_pullback_reversal_1300` | 51.5 | 69.6 | approve_for_testing |
| `midday_notional_trend_pullback_reversal_1200` | 50.0 | 66.8 | approve_for_testing |
| `morning_notional_trend_pullback_reversal_1030` | 52.7 | 73.7 | approve_for_testing |
| `morning_trade_trend_pullback_reversal_1030` | 53.3 | 71.6 | approve_for_testing |

Result: all five selected variants clear the pre-PnL 50 signals/year plausibility floor at every declared entry-grid corner. This does not evaluate profitability and does not promote the strategy.

Detailed CSV: `research_artifacts/es_trend_filtered_mes_participation_crowding_density_audit_20260618.csv`.

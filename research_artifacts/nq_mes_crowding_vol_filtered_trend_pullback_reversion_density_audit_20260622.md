# NQ MES-Crowding Volatility-Filtered Trend-Pullback Reversion Density Audit

Pre-PnL density audit only. No trade PnL, stop/target outcome, WFA result, or backtest metric was inspected for this NQ campaign before fixing the grid.

- Data: `data/cache/orderflow/nq_mes_participation_crowding_1m_20190506_20260612_full_rth_ny.csv`
- Lagged feature file: `data/external/nq_lagged_volatility_features_20110103_20260612.csv`
- Window: 2019-05-06 through 2026-06-12 (7.10 years)
- Signal timestamp: completed 10:29 ET bar for 10:30 ET next-bar entry
- Fixed trend threshold: 12 NQ ticks over the prior completed 09:45-10:15 trend window
- Tuned entry grid fixed before PnL: `share_rank_min=[0.35,0.45,0.55]`, `min_abs_return_ticks=[12,16,20]`

| Variant | Strict-corner min signals/year | Density decision |
|---|---:|---|
| exclude_extreme_vol20_trade_morning_1030 | 51.2533 | PASS |
| exclude_extreme_range10_trade_morning_1030 | 54.2102 | PASS |
| exclude_extreme_absret5_trade_morning_1030 | 52.2389 | PASS |
| exclude_extreme_downside20_trade_morning_1030 | 50.9717 | PASS |
| vol_downshift_trade_morning_1030 | 50.5492 | PASS |

CSV: `research_artifacts/nq_mes_crowding_vol_filtered_trend_pullback_reversion_density_audit_20260622.csv`

# NQ MES-Crowding Trend-Pullback Reversion Density Audit

Pre-PnL density audit only. No trade PnL, stop/target outcome, WFA result, or backtest metric was inspected before fixing this NQ grid.

- Data: `data/cache/orderflow/nq_mes_participation_crowding_1m_20190506_20260612_full_rth_ny.csv`
- Window: 2019-05-06 through 2026-06-12 (7.10 years)
- Tuned entry grid fixed before PnL: `share_rank_min=[0.35,0.45,0.55]`, `min_abs_return_ticks=[12,16,20]`
- Fixed trend thresholds: 12 NQ ticks for 15-minute morning variants; 24 NQ ticks for longer variants

| Variant | Strict-corner min signals/year | Density decision |
|---|---:|---|
| morning_trade_trend_pullback_reversal_1030 | 59.5608 | PASS |
| morning_notional_trend_pullback_reversal_1030 | 59.5608 | PASS |
| midday_notional_trend_pullback_reversal_1200 | 56.8855 | PASS |
| early_afternoon_notional_trend_pullback_reversal_1300 | 57.8711 | PASS |
| afternoon_notional_trend_pullback_reversal_1400 | 51.2533 | PASS |

CSV: `research_artifacts/nq_mes_crowding_trend_pullback_reversion_density_audit_20260622.csv`

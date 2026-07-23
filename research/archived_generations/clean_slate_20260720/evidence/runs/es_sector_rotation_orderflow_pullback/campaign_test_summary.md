# Campaign Test Summary

Campaign: `es_sector_rotation_orderflow_pullback`

Decision: **FAIL**

All five original variants and all five one-time stop-parameter-space rescues failed the limited_core_grid_test profitable-combination gate before monkey, WFA, Monte Carlo, simulated incubation, or frozen validation.

## Best Runs

- Best original: `financial_industrial_ema_pullback_large10_long_1500/run1` profitable_combo_rate=0.3333333333333333, benchmark_passing_combos=3, top_net=1587.5, PF=1.2620718118035492, MAR=0.4645667684858558, trades/year=56.13268963958591.
- Best rescue: `financial_industrial_ema_pullback_large10_long_1500/rescue1` profitable_combo_rate=0.6666666666666666, benchmark_passing_combos=7, top_net=1837.5, PF=1.2547660311958406, MAR=0.592991419475163, trades/year=56.13268963958591.

## Artifacts

- Results CSV: `backtest-campaigns/es_sector_rotation_orderflow_pullback/campaign_results.csv`
- Trade log manifest: `backtest-campaigns/es_sector_rotation_orderflow_pullback/trade_logs_manifest.csv`
- Equity curve manifest: `backtest-campaigns/es_sector_rotation_orderflow_pullback/equity_curves_manifest.csv`
- Density audit: `research_artifacts/es_sector_rotation_orderflow_pullback_density_audit_20260620.md`

No candidate_strategy_report.md was created because no run passed the staged methodology.

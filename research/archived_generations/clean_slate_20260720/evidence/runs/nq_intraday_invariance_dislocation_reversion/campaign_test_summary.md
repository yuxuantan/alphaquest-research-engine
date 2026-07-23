# NQ Intraday Invariance Dislocation Reversion Campaign Summary

Decision: FAIL

All five frozen NQ intraday trading-invariance dislocation variants failed `limited_core_grid_test`. Each variant tested 81 combinations, had 0 profitable combinations, 0 benchmark-passing combinations, and 0 Apex rule violating iterations. No variant reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

## Best Top-Combo By Variant

| variant_id                                       | profitable_combos | benchmark_pass_combos | top_net  | top_pf | top_trades | top_mar | top_failure_reason                          |
| ------------------------------------------------ | ----------------- | --------------------- | -------- | ------ | ---------- | ------- | ------------------------------------------- |
| opening_15m_two_sided_dislocation_fade_1130      | 0/81              | 0                     | -875.00  | 0.9680 | 305        | -0.1576 | min_total_net_profit;max_consecutive_losses |
| afternoon_15m_two_sided_dislocation_fade_1530    | 0/81              | 0                     | -1465.00 | 0.7968 | 179        | -0.7111 | min_total_net_profit                        |
| lunch_15m_two_sided_dislocation_fade_1330        | 0/81              | 0                     | -2085.00 | 0.6380 | 130        | -0.6535 | min_total_net_profit                        |
| full_session_15m_two_sided_dislocation_fade_1530 | 0/81              | 0                     | -2740.00 | 0.9420 | 459        | -0.3025 | min_total_net_profit;max_consecutive_losses |
| midday_30m_two_sided_dislocation_fade_1430       | 0/81              | 0                     | -4235.00 | 0.7732 | 280        | -0.6615 | min_total_net_profit                        |

Artifacts:

- Density audit: `research_artifacts/nq_intraday_invariance_dislocation_reversion_density_audit_20260623.md`
- Results CSV: `backtest-campaigns/nq_intraday_invariance_dislocation_reversion/campaign_results.csv`
- Aggregate JSON: `backtest-campaigns/nq_intraday_invariance_dislocation_reversion/campaign_test_summary.json`

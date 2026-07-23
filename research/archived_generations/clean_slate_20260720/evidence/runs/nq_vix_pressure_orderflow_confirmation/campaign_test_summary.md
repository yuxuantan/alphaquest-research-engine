# NQ VIX Pressure Orderflow Confirmation Campaign Summary

Decision: FAIL

All five frozen NQ VIX-pressure orderflow confirmation variants failed the staged flow. Three failed limited_core_grid_test; two passed core but failed limited_monkey_test. No run reached WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, acceptance, or candidate reporting.

## Best Top-Combo By Variant

| variant_id | terminal_stage | profitable_combos | benchmark_pass_combos | top_net | top_pf | top_trades | monkey_net_beat | monkey_dd_beat |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `vix_pressure_1200_large20_weakness_short` | limited_monkey_test | 27/27 | 0 | 2475.00 | 1.3181 | 75 | 0.8839 | 0.7326 |
| `vix_pressure_1130_vwap_signed_pressure_short` | limited_monkey_test | 27/27 | 10 | 1788.75 | 1.1752 | 85 | 0.8775 | 0.5834 |
| `vix_pressure_1030_large20_weakness_short` | limited_core_grid_test | 8/27 | 0 | 1260.00 | 1.1482 | 75 |  |  |
| `vix_pressure_1200_signed_weakness_short` | limited_core_grid_test | 4/27 | 0 | 602.50 | 1.0592 | 88 |  |  |
| `vix_pressure_1030_signed_weakness_short` | limited_core_grid_test | 3/27 | 0 | 642.50 | 1.0581 | 95 |  |  |

Artifacts:

- Density audit: `research_artifacts/nq_vix_pressure_orderflow_confirmation_density_audit_20260623.md`
- Results CSV: `backtest-campaigns/nq_vix_pressure_orderflow_confirmation/campaign_results.csv`
- Aggregate JSON: `backtest-campaigns/nq_vix_pressure_orderflow_confirmation/campaign_test_summary.json`

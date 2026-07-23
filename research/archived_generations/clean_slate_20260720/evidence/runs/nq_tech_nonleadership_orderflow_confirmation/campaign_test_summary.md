# NQ Tech Non-Leadership Orderflow Confirmation Campaign Summary

Decision: FAIL

All five frozen NQ tech non-leadership/orderflow-confirmation variants failed limited_core_grid_test. No run reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, acceptance, or candidate reporting.

## Best Top-Combo By Variant

| variant_id | terminal_stage | profitable_combos | benchmark_pass_combos | top_net | top_pf | top_trades | top_mar |
|---|---|---:|---:|---:|---:|---:|---:|
| `tech5d_nonleadership_1030_signed_flow_short` | limited_core_grid_test | 11/81 | 6 | 1677.50 | 1.3136 | 56 | 1.1378 |
| `tech5d_nonleadership_1130_signed_flow_short` | limited_core_grid_test | 25/81 | 7 | 1415.00 | 1.1842 | 75 | 0.7322 |
| `tech5d_nonleadership_1200_signed_flow_short` | limited_core_grid_test | 24/81 | 3 | 1240.00 | 1.1925 | 63 | 0.5327 |
| `tech5d_nonleadership_1130_vwap_signed_short` | limited_core_grid_test | 11/81 | 0 | 775.00 | 1.1652 | 48 | 0.3727 |
| `tech1d_nonleadership_1130_signed_flow_short` | limited_core_grid_test | 21/81 | 0 | 552.50 | 1.0668 | 76 | 0.2120 |

Artifacts:

- Density audit: `research_artifacts/nq_tech_nonleadership_orderflow_confirmation_density_audit_20260623.md`
- Results CSV: `backtest-campaigns/nq_tech_nonleadership_orderflow_confirmation/campaign_results.csv`
- Aggregate JSON: `backtest-campaigns/nq_tech_nonleadership_orderflow_confirmation/campaign_test_summary.json`

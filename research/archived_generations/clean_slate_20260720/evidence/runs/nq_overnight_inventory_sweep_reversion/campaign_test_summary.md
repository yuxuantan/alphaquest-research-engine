# NQ Overnight Inventory Sweep Reversion Campaign Summary

Decision: FAIL

All five frozen NQ overnight inventory sweep/reclaim variants failed `limited_core_grid_test`. No variant reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

## Best Top-Combo By Variant

| variant_id                              | profitable_combos | benchmark_pass_combos | top_net | top_pf | top_trades | top_mar | top_failure_reason                                                        |
| --------------------------------------- | ----------------- | --------------------- | ------- | ------ | ---------- | ------- | ------------------------------------------------------------------------- |
| extended_high_extreme_reject_short_1230 | 27/81             | 7                     | 1415.00 | 1.1722 | 87         | 0.3105  |                                                                           |
| morning_two_sided_extreme_reclaim_1130  | 5/81              | 0                     | 1170.00 | 1.0601 | 139        | 0.1763  | max_best_day_concentration                                                |
| morning_high_extreme_reject_short_1130  | 21/81             | 4                     | 1155.00 | 1.1363 | 78         | 0.3812  |                                                                           |
| morning_low_extreme_reclaim_long_1130   | 13/81             | 0                     | 210.00  | 1.0210 | 72         | 0.0407  | max_best_day_concentration                                                |
| extended_low_extreme_reclaim_long_1230  | 12/81             | 0                     | 195.00  | 1.1398 | 13         | 0.1701  | min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |

Artifacts:

- Density audit: `research_artifacts/nq_overnight_inventory_sweep_reversion_density_audit_20260623.md`
- Results CSV: `backtest-campaigns/nq_overnight_inventory_sweep_reversion/campaign_results.csv`
- Aggregate JSON: `backtest-campaigns/nq_overnight_inventory_sweep_reversion/campaign_test_summary.json`

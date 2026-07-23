# Campaign Test Summary

Campaign: `es_sector_opening_breadth_orderflow_continuation`

Decision: **FAIL**

All five originals failed. All five failed variants received one parameter-space-only rescue. No rescue passed the full staged workflow; broad_up rescue reached WFA and failed early-exit selection, cyclical_up rescue failed limited monkey/trade-path stress, and the remaining rescues failed limited core.

Original runs: 5; rescue runs: 5; passed runs: 0.
Best original: `broad_up_early_signed_long_1000/run1` with profitable combo rate 0.5679012345679012 and 4 benchmark-passing combos.
Best rescue: `broad_up_early_signed_long_1000/rescue1` with profitable combo rate 1.0 and terminal stage `walk_forward_analysis`.

Artifacts:
- campaign_results_csv: `backtest-campaigns/es_sector_opening_breadth_orderflow_continuation/campaign_results.csv`
- trade_logs_manifest_csv: `backtest-campaigns/es_sector_opening_breadth_orderflow_continuation/trade_logs_manifest.csv`
- equity_curves_manifest_csv: `backtest-campaigns/es_sector_opening_breadth_orderflow_continuation/equity_curves_manifest.csv`
- wfa_table_csv: `backtest-campaigns/es_sector_opening_breadth_orderflow_continuation/wfa_table.csv`
- monte_carlo_summary_csv: `backtest-campaigns/es_sector_opening_breadth_orderflow_continuation/monte_carlo_summary.csv`
- density_audit: `research_artifacts/es_sector_opening_breadth_orderflow_continuation_density_audit_20260620.md`
